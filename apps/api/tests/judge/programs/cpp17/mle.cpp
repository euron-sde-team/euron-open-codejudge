#include <vector>
#include <iostream>
int main() { std::vector<char> v(512u << 20); for (size_t i = 0; i < v.size(); i += 4096) v[i] = 1; std::cout << v.size(); }
