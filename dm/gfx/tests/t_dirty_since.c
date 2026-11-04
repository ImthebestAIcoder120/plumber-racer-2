// nvn_dirty_since's answer from a range's newest generation, and nvn_dirty_quiet_now: a sparse texture's look starts from the last time it was found clean, so a write after that time
// must always show, in a range written before it, in another page of the range, and through a write that faults. A page written earlier does not count from a later clean time.
#include "../nvn/nvn_dirty.h"
#include "../../host/dm.h"
#include <sys/mman.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

module_t *g_mod;
int g_nmod;
module_t *module_of(const void *p) { (void)p; return NULL; }
void crash_install(void);

static int g_fail;
#define EXPECT(name, want, got) do { long long want_ = (long long)(want), got_ = (long long)(got); \
    if (want_ != got_) { printf("FAIL: %s: expected %lld, got %lld\n", name, want_, got_); g_fail++; } else printf("PASS: %s\n", name); } while (0)

int main(void) {
    crash_install();
    size_t pg = (size_t)getpagesize(), n = pg * 16;
    uint8_t *m = mmap(NULL, n, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    uint8_t *other = mmap(NULL, n, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    if (m == MAP_FAILED || other == MAP_FAILED) return 1;
    nvn_dirty_add_range(m, n); nvn_dirty_add_range(other, n);
    uint64_t stamp = nvn_dirty_now(); nvn_dirty_protect(m, n); nvn_dirty_protect(other, n);
    EXPECT("nothing written yet", 0, nvn_dirty_since(m, n, stamp));
    uint64_t q0 = nvn_dirty_quiet_now();
    EXPECT("with no write under way there is a clean time", 1, q0 != 0);

    m[3 * pg] = 1;   // a write that faults
    EXPECT("the write shows from the upload", 1, nvn_dirty_since(m, n, stamp));
    EXPECT("the write shows from a clean time before it", 1, nvn_dirty_since(m, n, q0));
    EXPECT("another range does not see it", 0, nvn_dirty_since(other, n, q0));
    EXPECT("another page of the range does not see it", 0, nvn_dirty_since(m + 8 * pg, pg, q0));

    uint64_t q1 = nvn_dirty_quiet_now();
    EXPECT("after it, the clean time is later", 1, q1 > q0);
    EXPECT("the earlier write does not count from the later clean time", 0, nvn_dirty_since(m, n, q1));
    m[9 * pg] = 2;   // another page, in a range written before
    EXPECT("a new write in a range written before shows", 1, nvn_dirty_since(m, n, q1));
    EXPECT("in its own page", 1, nvn_dirty_since(m + 9 * pg, pg, q1));
    EXPECT("not in the page written before it", 0, nvn_dirty_since(m + 3 * pg, pg, q1));

    nvn_dirty_remove_range(m); nvn_dirty_add_range(m, n);   // the slot reused: all pages new again
    uint64_t q2 = nvn_dirty_quiet_now(); nvn_dirty_protect(m, n);
    EXPECT("a reused slot starts clean", 0, nvn_dirty_since(m, n, 0));
    m[pg] = 3;
    EXPECT("and shows its writes", 1, nvn_dirty_since(m, n, q2));
    printf("%s\n", g_fail ? "t_dirty_since: FAILED" : "t_dirty_since: all passed");
    return g_fail != 0;
}
