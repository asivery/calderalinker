void print(const char *data) {
    __asm__ volatile(
        "mov %0, %%eax\n"
        "out %%al, $0xff\n" :: "m"(data) : "eax"
    );
}
void printNumber(int data) {
    __asm__ volatile(
        "mov %0, %%eax\n"
        "out %%al, $0xfe\n" :: "r"(data) : "eax"
    );
}
