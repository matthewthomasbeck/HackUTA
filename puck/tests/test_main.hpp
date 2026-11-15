#pragma once

#include <cstdio>
#include <functional>
#include <string>
#include <vector>

namespace testing {
struct Case {
  const char* name;
  std::function<void()> fn;
};
inline std::vector<Case>& cases() {
  static std::vector<Case> c;
  return c;
}
inline int& failures() {
  static int f = 0;
  return f;
}
struct Registrar {
  Registrar(const char* n, std::function<void()> f) { cases().push_back({n, std::move(f)}); }
};
inline int run_all() {
  for (auto& c : cases()) {
    const int before = failures();
    try {
      c.fn();
    } catch (const std::exception& e) {
      std::printf("  EXCEPTION: %s\n", e.what());
      ++failures();
    }
    std::printf("%s %s\n", failures() == before ? "PASS" : "FAIL", c.name);
  }
  std::printf("%d failure(s)\n", failures());
  return failures() == 0 ? 0 : 1;
}
}  // namespace testing

#define TEST(name)                                                  \
  static void name();                                               \
  static testing::Registrar reg_##name(#name, name);                \
  static void name()

#define CHECK(cond)                                                          \
  do {                                                                       \
    if (!(cond)) {                                                           \
      std::printf("  CHECK failed %s:%d: %s\n", __FILE__, __LINE__, #cond);  \
      ++testing::failures();                                                 \
    }                                                                        \
  } while (0)
#define CHECK_EQ(a, b) CHECK((a) == (b))
