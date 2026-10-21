#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <pthread.h>

#include "common.h"
#include "db.h"
#include "protocol.h"
#include "session.h"

#define DEFAULT_PORT 5000
#define ACCEPT_POLL_MS 500
#define SEND_TIMEOUT_SEC 5

typedef struct {
    int         port;
    const char *db_path;
    const char *log_path;
} server_config_t;

static volatile sig_atomic_t g_stop = 0;

static void on_signal(int signo)
{
    (void)signo;
    g_stop = 1;
}

static void install_signals(void)
{
    struct sigaction action;

    memset(&action, 0, sizeof(action));
    action.sa_handler = on_signal;
    sigemptyset(&action.sa_mask);
    sigaction(SIGINT, &action, NULL);
    sigaction(SIGTERM, &action, NULL);

    // ignore SIGPIPE so writes to dead peers return EPIPE instead
    action.sa_handler = SIG_IGN;
    sigaction(SIGPIPE, &action, NULL);
}

static const char *env_or(const char *name, const char *fallback)
{
    const char *value = getenv(name);

    return value && *value ? value : fallback;
}

static int load_config(server_config_t *cfg, int argc, char **argv)
{
    const char *port_text = argc > 1 ? argv[1] : env_or("PORT", NULL);

    cfg->port = DEFAULT_PORT;
    cfg->db_path = env_or("DB_PATH", "./exam.db");
    cfg->log_path = env_or("LOG_PATH", "./server.log");
    if (!port_text) return 0;
    if (parse_int(port_text, &cfg->port) != 0 || cfg->port <= 0 || cfg->port > 65535) return -1;
    return 0;
}

static int open_listener(int port)
{
    struct sockaddr_in addr;
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    int yes = 1;

    if (fd < 0) return -1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons((uint16_t)port);

    // bind all interfaces so Docker port mapping reaches the server
    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0 || listen(fd, SOMAXCONN) < 0) {
        log_msg(LOG_ERROR, "bind/listen port %d failed: %s", port, strerror(errno));
        close(fd);
        return -1;
    }
    return fd;
}

static void configure_client(int fd)
{
    struct timeval timeout = { SEND_TIMEOUT_SEC, 0 };
    int yes = 1;

    // bound blocking sends so a stalled peer cannot freeze pushers
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));
}

static void *client_main(void *arg)
{
    session_t *sess = arg;
    char *buf = malloc(MAX_PAYLOAD + 1);
    uint32_t len = 0;
    int rc = FRAME_ERROR;

    while (buf) {
        rc = recv_frame(sess->fd, buf, MAX_PAYLOAD + 1, &len);
        if (rc != FRAME_OK) break;
        protocol_handle(sess, buf);
    }
    if (rc == FRAME_TOO_LONG) session_send(sess, "ERR|LINE_TOO_LONG|frame exceeds 8192 bytes");
    if (rc == FRAME_TOO_LONG || rc == FRAME_EMPTY) log_msg(LOG_WARN, "fd=%d malformed frame rc=%d, closing", sess->fd, rc);
    protocol_disconnect(sess);
    free(buf);
    return NULL;
}

static int spawn_worker(session_t *sess)
{
    sigset_t block;
    sigset_t previous;
    int rc = 0;

    // keep shutdown signals on the main thread only
    sigemptyset(&block);
    sigaddset(&block, SIGINT);
    sigaddset(&block, SIGTERM);
    pthread_sigmask(SIG_BLOCK, &block, &previous);
    rc = pthread_create(&sess->thread, NULL, client_main, sess);
    pthread_sigmask(SIG_SETMASK, &previous, NULL);
    return rc;
}

static void accept_client(int listen_fd)
{
    struct sockaddr_in peer;
    socklen_t peer_len = sizeof(peer);
    int fd = accept(listen_fd, (struct sockaddr *)&peer, &peer_len);
    session_t *sess = NULL;

    if (fd < 0) return;
    configure_client(fd);
    sess = session_reserve(fd);
    if (!sess) {
        log_msg(LOG_WARN, "fd=%d rejected, %d clients connected", fd, MAX_CLIENTS);
        send_text(fd, "ERR|INTERNAL|server full");
        close(fd);
        return;
    }
    log_msg(LOG_INFO, "fd=%d connected from %s:%d", fd, inet_ntoa(peer.sin_addr), ntohs(peer.sin_port));
    if (spawn_worker(sess) == 0) return;
    log_msg(LOG_ERROR, "fd=%d thread spawn failed", fd);
    session_release_unstarted(sess);
}

static void accept_loop(int listen_fd)
{
    struct pollfd pfd = { listen_fd, POLLIN, 0 };

    while (!g_stop) {
        int ready = poll(&pfd, 1, ACCEPT_POLL_MS);

        sessions_reap();
        if (ready > 0 && (pfd.revents & POLLIN)) accept_client(listen_fd);
    }
}

static void drain_workers(void)
{
    struct timespec pause = { 0, 20 * 1000 * 1000 };

    // unblock every recv so workers run their disconnect cleanup
    sessions_shutdown_all();
    while (sessions_active_count() > 0) {
        sessions_reap();
        nanosleep(&pause, NULL);
    }
    sessions_reap();
}

static void shutdown_server(int listen_fd)
{
    if (listen_fd >= 0) close(listen_fd);
    drain_workers();
    db_close();
    sessions_destroy();
    log_msg(LOG_INFO, "server stopped");
    log_close();
}

int main(int argc, char **argv)
{
    server_config_t cfg;
    int listen_fd = -1;
    int rc = 1;

    memset(&cfg, 0, sizeof(cfg));
    if (load_config(&cfg, argc, argv) != 0) {
        fprintf(stderr, "usage: %s [port 1-65535]\n", argv[0]);
        return 2;
    }
    log_open(cfg.log_path, 1);
    install_signals();
    sessions_init();
    if (db_open(cfg.db_path) != DB_OK || db_seed_defaults() != DB_OK) goto cleanup;
    listen_fd = open_listener(cfg.port);
    if (listen_fd < 0) goto cleanup;

    log_msg(LOG_INFO, "listening on 0.0.0.0:%d", cfg.port);
    accept_loop(listen_fd);
    rc = 0;

cleanup:
    shutdown_server(listen_fd);
    return rc;
}
