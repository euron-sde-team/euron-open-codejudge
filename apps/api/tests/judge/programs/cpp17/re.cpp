#include <cstdlib>
int main() { int* p = nullptr; volatile int x = *p; return x; }
