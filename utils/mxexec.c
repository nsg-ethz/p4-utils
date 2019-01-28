/* mnexec: execution utility for MiniNExT
 * (MiniNet ExTended)
 *
 * Adds support to the default Mininet for:
 *
 *  - PID namespaces
 *  - UTS namespaces
 *  - additional mount namespaces
 *
 * Partially based on public domain setsid(1)
 * Also based on public domain util-linux unshare.c & nsenter.c

 # Credit to MiniNext: https://github.com/USC-NSL/miniNExT
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <linux/sched.h>
#include <unistd.h>
#include <limits.h>
#include <syscall.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sched.h>
#include <ctype.h>
#include <sys/wait.h>
#include <sys/mount.h>

#if !defined(VERSION)
#define VERSION "(devel)"
#endif

#define TRUE            1
#define FALSE           0
#define NET_NS_CREATE   1
#define NET_NS_JOIN     2
#define PID_NS_CREATE   1
#define PID_NS_JOIN     2
#define MOUNT_NS_CREATE 1
#define MOUNT_NS_JOIN   2

void usage(char *name) {
    printf(
            "Execution utility for MiniNExT (MiniNet ExTended)\n\n"
            "Usage: %s [-cdnmiufp] [-a pid] [-b pid] [-k pid] [-j pid] [-g group] [-r rtprio] cmd args...\n\n"
            "Options:\n"
            "  -c: close all file descriptors except stdin/out/error\n"
            "  -d: detach from tty by calling setsid()\n"
            "  -n: run in new network namespace\n"
            "  -m: run in new mount namespace\n"
            "  -i: run in new PID namespace\n"
            "  -u: run in new UTS namespace\n"
            "  -f: mount procfs (requires new PID namespace)\n"
            "  -p: print ^A + pid\n"
            "  -a: pid: attach to pid's network namespace\n"
            "  -b: pid: attach to pid's mount namespace\n"
            "  -k: pid: attach to pid's PID namespace\n"
            "  -j: pid: attach to pid's UTS namespace\n"
            "  -g: group: add to cgroup\n"
            "  -r: rtprio: run with SCHED_RR (usually requires -g)\n"
            "  -v: print version\n", name);
}

int setns(int fd, int nstype) {
    return syscall(__NR_setns, fd, nstype);
}

/* Validate alphanumeric path foo1/bar2/baz */
void validate(char *path) {
    char *s;
    for (s = path; *s; s++) {
        if (!isalnum(*s) && *s != '/') {
            fprintf(stderr, "invalid path: %s\n", path);
            exit(1);
        }
    }
}

/* Add our pid to cgroup */
void cgroup(char *gname) {
    static char path[PATH_MAX];
    static char *groups[] = { "cpu", "cpuacct", "cpuset", NULL };
    char **gptr;
    pid_t pid = getpid();
    int count = 0;
    validate(gname);
    for (gptr = groups; *gptr; gptr++) {
        FILE *f;
        snprintf(path, PATH_MAX, "/sys/fs/cgroup/%s/%s/tasks", *gptr, gname);
        f = fopen(path, "w");
        if (f) {
            count++;
            fprintf(f, "%d\n", pid);
            fclose(f);
        }
    }
    if (!count) {
        fprintf(stderr, "cgroup: could not add to cgroup %s\n", gname);
        exit(1);
    }
}

/* Attach to the specified namespace FD path */
int attachToNS(char *path) {
    int nsid;
    nsid = open(path, O_RDONLY);
    if (nsid < 0) {
        perror(path);
        return 1;
    }
    if (setns(nsid, 0) != 0) {
        perror("setns");
        return 1;
    }
    return 0;
}

int main(int argc, char *argv[]) {
    int c;
    int fd;
    char path[PATH_MAX];
    int pid;
    int detach = 0;
    int netns = 0;
    int mountns = 0;
    int mountnspid = 0;
    int pidns = 0;
    int printpid = 0;
    int mountprocfs = 0;
    static struct sched_param sp;
    while ((c = getopt(argc, argv, "+cdnmiufpa:b:k:j:g:r:vh")) != -1)
        switch (c) {
        case 'c':
            /* close file descriptors except stdin/out/error */
            for (fd = getdtablesize(); fd > 2; fd--)
                close(fd);
            break;
        case 'd':
            /* detach from tty */
            detach = 1; /* delay setsid() incase new PID namespace */
            break;
        case 'n':
            /* run in network namespace */
            if (unshare(CLONE_NEWNET) == -1) {
                perror("unshare");
                return 1;
            }
            netns = NET_NS_CREATE;
            break;
        case 'm':
            /* run in mount namespace */
            if (unshare(CLONE_NEWNS) == -1) {
                perror("unshare");
                return 1;
            }
            /* mount sysfs to pick up the new network namespace */
            mountns = MOUNT_NS_CREATE; /* delay mount of /sysfs */
            break;
        case 'i':
            /* run in new PID namespace */
            if (unshare(CLONE_NEWPID) == -1) {
                perror("unshare");
                return 1;
            }
            pidns = PID_NS_CREATE; /* record creation of PID namespace */
            break;
        case 'u':
            /* run in new UTS namespace */
            if (unshare(CLONE_NEWUTS) == -1) {
                perror("unshare");
                return 1;
            }
            break;
        case 'f':
            /* mount procfs (for new PID namespaces) */
            mountprocfs = TRUE; /* delay mounting proc until new NS established */
            break;
        case 'p':
            /* print pid */
            printpid = TRUE; /* delay printing PID until after NS procesisng*/
            break;
        case 'a':
            /* Attach to pid's network namespace */
            pid = atoi(optarg);
            sprintf(path, "/proc/%d/ns/net", pid);
            if (attachToNS(path) != 0) {
                return 1;
            }
            netns = NET_NS_JOIN;
            break;
        case 'b':
            /* Attach to pid's mount namespace */
            mountns = MOUNT_NS_JOIN; /* delay joining mount namespace */
            mountnspid = atoi(optarg); /* record PID to join */
            break;
        case 'k':
            /* Attach to pid's PID namespace */
            pid = atoi(optarg);
            sprintf(path, "/proc/%d/ns/pid", pid);
            if (attachToNS(path) != 0) {
                return 1;
            }
            pidns = PID_NS_JOIN; /* record join of PID namespace */
            break;
        case 'j':
            /* Attach to pid's UTS namespace */
            pid = atoi(optarg);
            sprintf(path, "/proc/%d/ns/uts", pid);
            if (attachToNS(path) != 0) {
                return 1;
            }
            break;
        case 'g':
            /* Attach to cgroup */
            cgroup(optarg);
            break;
        case 'r':
            /* Set RT scheduling priority */
            sp.sched_priority = atoi(optarg);
            if (sched_setscheduler(getpid(), SCHED_RR, &sp) < 0) {
                perror("sched_setscheduler");
                return 1;
            }
            break;
        case 'v':
            printf("%s\n", VERSION);
            exit(0);
        case 'h':
            usage(argv[0]);
            exit(0);
        default:
            usage(argv[0]);
            exit(1);
        }

    /* fork to create / join PID namespace */
    if (pidns == PID_NS_CREATE || pidns == PID_NS_JOIN) {
        int status = 0;
        pid_t pid = fork();
        switch (pid) {
        case -1:
            perror("fork");
            return 1;
        case 0: /* child */
            break;
        default: /* parent */
            /* print global PID (not namespace PID)*/
            if (printpid == 1) {
                printf("\001%d\n", pid);
                fflush(stdout);
            }
            /* wait on the PID to handle attachment for 'mx'*/
            if (waitpid(pid, &status, 0) == -1)
                return 1;
            if (WIFEXITED(status))
                /* caught child exit, forward return code*/
                return WEXITSTATUS(status);
            else if (WIFSIGNALED(status))
                kill(getpid(), WTERMSIG(status));
            /* child exit failed, (although return won't distinguish) */
            return 1;
        }
    }

    /* if requested, we are in the new/requested PID namespace */
    /* completed performing other namespaces (PID/network) operations */

    /* go ahead and join the mount namespace if requested */
    if (mountns == MOUNT_NS_JOIN && mountnspid != FALSE) {
        sprintf(path, "/proc/%d/ns/mnt", pid);
        if (attachToNS(path) != 0) {
            return 1;
        }
    }

    /* if mount of procfs requested, check for pidns and mountns */
    if (mountprocfs && (pidns != PID_NS_CREATE || mountns != MOUNT_NS_CREATE)) {
        /* requested procfs, but required PID and/or mount namespace missing  */
        return 1;
    }

    /* mount procfs to pick up the new PID namespace */
    if (mountprocfs
            && (mount("none", "/proc", NULL, MS_PRIVATE | MS_REC, NULL) != 0
                    || mount("proc", "/proc", "proc",
                            MS_NOSUID | MS_NOEXEC | MS_NODEV, NULL) != 0)) {
        perror("mount");
    }

    /* mount sysfs to pick up the new PID namespace */
    if (netns == NET_NS_CREATE && mountns == MOUNT_NS_CREATE) {
        if (mount("sysfs", "/sys", "sysfs", MS_MGC_VAL, NULL) == -1) {
            perror("mount");
            return 1;
        }
    }

    /* setsid() if requested & required (not needed if using PID namespace) */
    if (detach == 1 && pidns == FALSE) {
        if (getpgrp() == getpid()) {
            switch (fork()) {
            case -1:
                perror("fork");
                return 1;
            case 0: /* child */
                break;
            default: /* parent */
                return 0;
            }
        }
        setsid();
    }

    /* print pid if requested (if in new namespace, we don't print local PID) */
    if (printpid == 1 && pidns == 0) {
        printf("\001%d\n", getpid());
        fflush(stdout);
    }

    /* launch if requested */
    if (optind < argc) {
        execvp(argv[optind], &argv[optind]);
        perror(argv[optind]);
        return 1;
    }

    usage(argv[0]);

    return 0;
}