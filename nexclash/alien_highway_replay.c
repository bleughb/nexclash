/* Compiled beside an instrumented copy of OverSpec's classic/nx.c. */
#include "exclude.inc"
#include "observed.c"
#include <inttypes.h>
#include <zlib.h>

struct __attribute__((packed)) Record {
  uint32_t fetches, reads;
  uint16_t pc, sp, af, bc, de, hl, ix, iy, af2, bc2, de2, hl2;
  uint8_t i, r, iff, im;
  uint32_t crc;
};
static FILE *inputs, *frames;
static struct Record expected;
static unsigned long read_count, record_count, checks, splits, reg_errors,
    ram_errors;
static unsigned long long beam_visible, beam_wrong, visible, wrong;
static unsigned long bad_frames, bad_beam_frames, on_frames, copy_count, shows,
    missing_shows;
static int started, finished, negative, baseline;
static FILE *paired;
static unsigned long pair_frames, pair_hooks, flag_only;
static uint32_t actual_crc, io_hash, screen_reads, sound_writes;
static long long first_tick, last_tick;
static long long ticks(void) {
  return (long long)S.frames * 8 * frameT + S.m28;
}
static void hash_event(uint16_t address, uint8_t value) {
  io_hash = 16777619u * (io_hash ^ address);
  io_hash = 16777619u * (io_hash ^ value);
}
static uint8_t game_read(uint16_t address, uint8_t value) {
  if (started && !finished && address >= 0x4000 && address < 0x5b00 &&
      nxPc() >= 0x4000) {
    screen_reads++;
    hash_event(address, value);
  }
  return value;
}
static void game_out(uint16_t port, uint8_t value) {
  if (started && !finished && !(port & 1) && nxPc() >= 0x4000) {
    sound_writes++;
    hash_event(port, value);
  }
}
static void check_pair(int type) {
  struct {
    uint16_t words[12];
    uint8_t extra[4];
    uint32_t crc, bus, screen, sound, iff2;
  } actual = {{z.pc, z.sp, z.a * 256 + z.f, BC, DE, HL, z.ix, z.iy,
               z.a_ * 256 + z.f_, z.b_ * 256 + z.c_, z.d_ * 256 + z.e_,
               z.h_ * 256 + z.l_},
              {z.i, IR() & 255, z.iff1, z.im},
              actual_crc,
              io_hash,
              screen_reads,
              sound_writes,
              z.iff2},
    reference;
  if (baseline) {
    if (fwrite(&actual, sizeof actual, 1, paired) != 1)
      exit(11);
  } else if (!fread(&reference, sizeof reference, 1, paired) ||
             memcmp(&actual, &reference, sizeof actual)) {
    fprintf(stderr,
            "paired state mismatch frame=%lu pc=%04x kind=%d RAM=%08x/%08x\n",
            record_count, z.pc, type, actual.crc, reference.crc);
    exit(11);
  }
  if (type)
    pair_hooks++;
  else
    pair_frames++;
}
static unsigned long long before_beam;
static const struct {
  uint16_t pc;
  uint8_t size, fetches;
} sites[] = {
#include "sites.inc"
};
static uint8_t site_id[65536], interior[65536];
static unsigned pending_fetches;
static int active_site, original_pc;
static uint32_t remaining;

static uint8_t read_game(uint16_t port, uint8_t native) {
  if (!started || original_pc < 0x4000 || finished)
    return native;
  int lo = fgetc(inputs), hi = fgetc(inputs), value = fgetc(inputs);
  if (value < 0 || (lo + 256 * hi) != port) {
    fprintf(stderr,
            "input mismatch read=%lu pc=%04x expected=%02x%02x observed=%04x\n",
            read_count, original_pc, hi, lo, port);
    exit(2);
  }
  read_count++;
  return value;
}
static void compare_beam(int row, int l, int r) {
  if (!started || finished || row < 32 || row >= 224)
    return;
  for (int x = l; x < r; x++)
    if (lnS[x] != TRANSP) {
      beam_visible++;
      if (lnU[x] != lnS[x]) {
        if (beam_wrong < 4)
          fprintf(stderr, "beam frame %d x%d y%d U=%x S=%x\n", S.frames, x - 32,
                  row - 32, lnU[x], lnS[x]);
        beam_wrong++;
      }
    }
}
/* Build coverage from the source masks in original game RAM, independently
 * of the assembler's mask pages, tile table and 4-bit pattern encoder. */
static uint8_t ownership[65536], road[18][32];
static unsigned long long commit_pixels;
static unsigned long coverage_errors;
static unsigned char read_ram(int a) { return rp[(a & 65535) >> 13][a & 8191]; }
static void record_plot(int pc) {
  for (int row = 0; row < 24; row++) {
    int src = DE + row * 6, dst = (BC - row * 32) & 65535;
    uint32_t mask = 0, ink = 0;
    for (int j = 0; j < 3; j++) {
      mask = (mask << 8) | read_ram(src + j);
      ink = (ink << 8) | read_ram(src + j + 3);
    }
    if (pc == 0x8fd5) {
      mask = (mask >> 2) | ((mask & 0x800000) ? 0xc00000 : 0);
      ink >>= 2;
    } else {
      int shift = pc == 0x9073 ? 4 : pc == 0x90c8 ? 2 : 0, carry = 1;
      for (int j = 0; j < shift; j++) {
        int next = (mask >> 23) & 1;
        mask = (mask << 1) | carry;
        carry = next;
      }
      ink <<= shift;
    }
    uint32_t solid = ~mask | ink;
    for (int j = 0; j < (pc == 0x9073 ? 2 : 3); j++)
      ownership[(dst + j) & 65535] |= (solid >> (16 - 8 * j)) & 255;
  }
}
static void pixels(int commit) {
  uint8_t seen[144][32] = {{0}};
  unsigned long n = 0, bad = 0;
  if (S.nr[0x15] & 1)
    for (int j = 0; j < 128; j++) {
      uint8_t *a = S.attr[j];
      if (!(a[3] & 128))
        continue;
      if ((a[3] & 192) != 192 || (a[4] & 191) != 128 || (a[2] & 254)) {
        fprintf(stderr, "unexpected sprite mode\n");
        exit(3);
      }
      unsigned pat = ((a[3] & 63) * 2 + ((a[4] >> 6) & 1)) * 128;
      int x0 = a[0] + ((a[2] & 1) << 8) - 32, y0 = (int)a[1] - 32;
      for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++) {
          int px = x0 + x, py = y0 + y, b = S.pattern[pat + y * 8 + x / 2],
              v = (x & 1) ? (b & 15) : (b >> 4);
          if (v == (S.nr[0x4b] & 15))
            continue;
          if ((unsigned)px >= 256 || (unsigned)py >= 192) {
            fprintf(stderr, "sprite outside paper\n");
            exit(4);
          }
          const uint8_t *ula = ram + 10 * PAGE;
          int bitmap =
              ula[(py & 7) * 256 + (py & 56) * 4 + (py & 192) * 32 + px / 8];
          int attr = ula[6144 + (py / 8) * 32 + px / 8],
              ink = bitmap & (128 >> (px & 7));
          int idx = ulaStandardIndex(attr, ink, (S.frames >> 4) & 1);
          if (commit && py < 144)
            seen[py][px / 8] |= 128 >> (px & 7);
          n++;
          bad += S.pal[2][v] != S.pal[0][idx];
        }
    }
  if (commit) {
    for (int y = 0; y < 144; y++)
      for (int x = 0; x < 32; x++) {
        uint8_t want = road[y / 8][x] ? ownership[0xe900 + 32 * y + x] : 0;
        if (seen[y][x] != want)
          coverage_errors++;
      }
    coverage_errors += bad;
    commit_pixels += n;
    return;
  }
  visible += n;
  wrong += bad;
  bad_frames += !!bad;
  on_frames += !!n;
}
static uint32_t ram_checksum(void) {
  uint8_t data[49152];
  /* Compare game RAM as mapped after the wrapper restores the MMU. */
  for (int slot = 2; slot < 8; slot++)
    memcpy(data + (slot - 2) * PAGE, rp[slot], PAGE);
  for (unsigned i = 0; i < sizeof sites / sizeof *sites; i++)
    memset(data + sites[i].pc - 0x4000, 0, sites[i].size);
  memset(data + TAIL_OFFSET, 0, TAIL_LENGTH);
  return crc32(0, data, sizeof data);
}
static void advance_frame(int split) {
  last_tick = ticks();
  pixels(0);
  record_count++;
  if (read_count != expected.reads) {
    fprintf(stderr, "input count mismatch frame %lu (%lu/%u)\n", record_count,
            read_count, expected.reads);
    exit(5);
  }
  if (split)
    splits++;
  else {
    checks++;
    uint16_t a[] = {z.pc,
                    z.sp,
                    z.a * 256 + z.f,
                    BC,
                    DE,
                    HL,
                    z.ix,
                    z.iy,
                    z.a_ * 256 + z.f_,
                    z.b_ * 256 + z.c_,
                    z.d_ * 256 + z.e_,
                    z.h_ * 256 + z.l_};
    actual_crc = ram_checksum();
    check_pair(0);
    uint16_t delta_f = a[2] ^ expected.af;
    if (delta_f && !(delta_f & ~0x28)) {
      flag_only++;
      a[2] = expected.af;
    }
    if (memcmp(a, &expected.pc, 24) || z.i != expected.i ||
        (IR() & 255) != expected.r || z.iff1 != expected.iff ||
        z.im != expected.im) {
      if (reg_errors++ < 5) {
        fprintf(stderr, "register frame=%lu", record_count);
        for (int i = 0; i < 12; i++)
          fprintf(stderr, " %04x/%04x", a[i],
                  ((uint16_t *)((char *)&expected + 8))[i]);
        fprintf(stderr, " R%02x/%02x\n", IR() & 255, expected.r);
      }
      if (z.pc != expected.pc) {
        fprintf(stderr, "PC divergence frame %lu\n", record_count);
        exit(6);
      }
    }
    uint32_t crc = actual_crc;
    if (crc != expected.crc && ram_errors++ < 4)
      fprintf(stderr, "RAM frame=%lu pc=%04x %08x/%08x\n", record_count, z.pc,
              crc, expected.crc);
  }
  if (!fread(&expected, sizeof expected, 1, frames)) {
    if (ferror(frames))
      exit(1);
    finished = 1;
    return;
  }
  remaining = expected.fetches;
  if (!remaining)
    advance_frame(0); /* An RZX can end in a zero-fetch frame. */
}
static void pre_step(void) {
  original_pc = z.pc;
  if (finished)
    return;
  if (!started) {
    if (z.pc != 0x89ca)
      return;
    started = 1;
    first_tick = ticks();
    for (int t = 0x8700; t < 0x877e; t += 7) {
      int off = read_ram(t + 1) + 256 * read_ram(t + 2) - 0xe900;
      for (int j = 0; j < read_ram(t); j++)
        road[off / 256][(off - j) & 31] = 1;
    }
  }
  if (active_site &&
      z.pc == sites[active_site - 1].pc + sites[active_site - 1].size) {
    actual_crc = ram_checksum();
    check_pair(1);
    if (sites[active_site - 1].pc == 0x919a) {
      if (!baseline)
        pixels(1);
      shows++;
      missing_shows += !baseline && !(S.nr[0x15] & 1);
    }
    pending_fetches = sites[active_site - 1].fetches;
    active_site = 0;
  }
  if (pending_fetches) {
    if (pending_fetches >= remaining) {
      int split = expected.pc != z.pc && pending_fetches > remaining;
      if (split && !(expected.pc < z.pc && z.pc - expected.pc < 4)) {
        fprintf(stderr, "unexpected interior frame at %04x/%04x\n", expected.pc,
                z.pc);
        exit(6);
      }
      unsigned extra = split ? pending_fetches - remaining : 0;
      advance_frame(split);
      remaining -= extra;
    } else
      remaining -= pending_fetches;
    pending_fetches = 0;
  }
  if (finished || active_site)
    return;
  if (interior[z.pc]) {
    fprintf(stderr, "jump into patch at %04x\n", z.pc);
    exit(6);
  }
  if (site_id[z.pc]) {
    if (z.pc == 0x8f6c || z.pc == 0x8c42)
      memset(ownership, 0, sizeof ownership);
    if (z.pc == 0x8fd5 || z.pc == 0x9073 || z.pc == 0x90c8 || z.pc == 0x9112)
      record_plot(z.pc);
    active_site = site_id[z.pc];
    copy_count += (z.pc == 0x913d);
    return;
  }
  unsigned op = rp[z.pc >> 13][z.pc & 8191];
  pending_fetches = 1 + (op == 0xcb || op == 0xed || op == 0xdd || op == 0xfd);
}
static uint8_t *file_bytes(const char *name, size_t *size) {
  FILE *f = fopen(name, "rb");
  if (!f) {
    perror(name);
    exit(1);
  }
  fseek(f, 0, SEEK_END);
  *size = ftell(f);
  rewind(f);
  uint8_t *data = malloc(*size);
  if (!data || fread(data, 1, *size, f) != *size)
    exit(1);
  fclose(f);
  return data;
}
int main(int argc, char **argv) {
  if (argc != 6)
    return 1;
  negative = atoi(argv[4]) == 1;
  baseline = atoi(argv[4]) == 2;
  paired = fopen(argv[5], baseline ? "wb" : "rb");
  if (!paired)
    return 1;
  for (unsigned i = 0; i < sizeof sites / sizeof *sites; i++) {
    site_id[sites[i].pc] = i + 1;
    for (unsigned j = 1; j < sites[i].size; j++)
      interior[sites[i].pc + j] = 1;
  }
  inputs = fopen(argv[2], "rb");
  frames = fopen(argv[3], "rb");
  if (!inputs || !frames || !fread(&expected, sizeof expected, 1, frames))
    return 1;
  remaining = expected.fetches;
  size_t size;
  uint8_t *data = file_bytes(argv[1], &size);
  const char *err = nx_load(data, size);
  if (err) {
    fprintf(stderr, "%s\n", err);
    return 1;
  }
  while (!finished && S.frames < 85000) {
    before_beam = beam_wrong;
    nx_frame();
    bad_beam_frames += beam_wrong != before_beam;
    if (S.frames % 5000 == 0) {
      printf("physical=%d recorded=%lu wrong=%llu beam_wrong=%llu\n", S.frames,
             record_count, wrong, beam_wrong);
      fflush(stdout);
    }
  }
  printf("physical=%d recorded=%lu inputs=%lu states=%lu interior=%lu "
         "reg_errors=%lu ram_errors=%lu visible_frames=%lu visible_pixels=%llu "
         "wrong_frames=%lu wrong_pixels=%llu beam_pixels=%llu beam_wrong=%llu "
         "beam_wrong_frames=%lu copies=%lu publishes=%lu missing_shows=%lu\n",
         S.frames, record_count, read_count, checks, splits, reg_errors,
         ram_errors, on_frames, visible, bad_frames, wrong, beam_visible,
         beam_wrong, bad_beam_frames, copy_count, shows, missing_shows);
  printf("paired_frames=%lu hook_returns=%lu cross_core_flag_only=%lu\n",
         pair_frames, pair_hooks, flag_only);
  printf("commit_pixels=%llu coverage_errors=%lu screen_reads=%u "
         "even_port_writes=%u elapsed_ticks=%lld\n",
         commit_pixels, coverage_errors, screen_reads, sound_writes,
         last_tick - first_tick);
  return !finished || (!baseline && (!beam_visible || !commit_pixels)) ||
         coverage_errors || reg_errors || ram_errors || missing_shows ||
         (!baseline && !on_frames) ||
         (negative ? (!wrong || !beam_wrong) : wrong || beam_wrong);
}
