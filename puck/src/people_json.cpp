#include "people_json.hpp"

#include <cctype>
#include <string_view>

namespace calypso {
namespace {

using View = std::string_view;

void skip_ws(View s, std::size_t& i) {
  while (i < s.size() && std::isspace(static_cast<unsigned char>(s[i]))) {
    ++i;
  }
}

bool consume(View s, std::size_t& i, char c) {
  skip_ws(s, i);
  if (i >= s.size() || s[i] != c) {
    return false;
  }
  ++i;
  return true;
}

bool parse_string(View s, std::size_t& i, std::string& out) {
  skip_ws(s, i);
  if (i >= s.size() || s[i] != '"') {
    return false;
  }
  ++i;
  out.clear();
  while (i < s.size()) {
    const char c = s[i++];
    if (c == '"') {
      return true;
    }
    if (c == '\\') {
      if (i >= s.size()) {
        return false;
      }
      const char e = s[i++];
      switch (e) {
        case 'n': out.push_back('\n'); break;
        case 'r': out.push_back('\r'); break;
        case 't': out.push_back('\t'); break;
        case 'u':
          // Names are ASCII for the MVP; keep a placeholder.
          for (int k = 0; k < 4 && i < s.size(); ++k) {
            ++i;
          }
          out.push_back('?');
          break;
        default: out.push_back(e); break;  // \" \\ \/ and anything else
      }
      continue;
    }
    out.push_back(c);
  }
  return false;
}

// Skips any JSON value (string, number, literal, nested array/object).
bool skip_value(View s, std::size_t& i) {
  skip_ws(s, i);
  if (i >= s.size()) {
    return false;
  }
  const char c = s[i];
  if (c == '"') {
    std::string junk;
    return parse_string(s, i, junk);
  }
  if (c == '[' || c == '{') {
    const char close = c == '[' ? ']' : '}';
    ++i;
    skip_ws(s, i);
    if (i < s.size() && s[i] == close) {
      ++i;
      return true;
    }
    while (i < s.size()) {
      if (c == '{') {
        std::string key;
        if (!parse_string(s, i, key) || !consume(s, i, ':')) {
          return false;
        }
      }
      if (!skip_value(s, i)) {
        return false;
      }
      skip_ws(s, i);
      if (i < s.size() && s[i] == ',') {
        ++i;
        continue;
      }
      if (i < s.size() && s[i] == close) {
        ++i;
        return true;
      }
      return false;
    }
    return false;
  }
  // number / true / false / null
  const std::size_t start = i;
  while (i < s.size() && (std::isalnum(static_cast<unsigned char>(s[i])) ||
                          s[i] == '-' || s[i] == '+' || s[i] == '.')) {
    ++i;
  }
  return i > start;
}

bool parse_person(View s, std::size_t& i, PersonRef& p) {
  p = {};
  if (!consume(s, i, '{')) {
    return false;
  }
  skip_ws(s, i);
  if (i < s.size() && s[i] == '}') {
    ++i;
    return false;  // no id
  }
  while (i < s.size()) {
    std::string key;
    if (!parse_string(s, i, key) || !consume(s, i, ':')) {
      return false;
    }
    skip_ws(s, i);
    if (key == "id" || key == "name") {
      std::string v;
      if (i < s.size() && s[i] == '"') {
        if (!parse_string(s, i, v)) {
          return false;
        }
      } else if (!skip_value(s, i)) {  // null etc.
        return false;
      }
      (key == "id" ? p.id : p.name) = v;
    } else if (key == "is_patient") {
      if (s.substr(i, 4) == "true") {
        p.is_patient = true;
        i += 4;
      } else if (s.substr(i, 5) == "false") {
        p.is_patient = false;
        i += 5;
      } else if (!skip_value(s, i)) {
        return false;
      }
    } else if (!skip_value(s, i)) {
      return false;
    }
    skip_ws(s, i);
    if (i < s.size() && s[i] == ',') {
      ++i;
      continue;
    }
    if (i < s.size() && s[i] == '}') {
      ++i;
      return !p.id.empty();
    }
    return false;
  }
  return false;
}

std::string lower(std::string s) {
  for (auto& c : s) {
    c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
  }
  return s;
}

}  // namespace

bool parse_people(const std::string& json, std::vector<PersonRef>& out) {
  out.clear();
  const View s(json);
  std::size_t i = 0;
  if (!consume(s, i, '[')) {
    return false;
  }
  skip_ws(s, i);
  if (i < s.size() && s[i] == ']') {
    return true;
  }
  while (i < s.size()) {
    PersonRef p;
    if (!parse_person(s, i, p)) {
      out.clear();
      return false;
    }
    out.push_back(std::move(p));
    skip_ws(s, i);
    if (i < s.size() && s[i] == ',') {
      ++i;
      continue;
    }
    if (i < s.size() && s[i] == ']') {
      return true;
    }
    break;
  }
  out.clear();
  return false;
}

std::optional<std::string> find_person_id(const std::vector<PersonRef>& people,
                                          const std::string& name,
                                          std::string& error) {
  const std::string want = lower(name);
  const PersonRef* hit = nullptr;
  int n = 0;
  for (const auto& p : people) {
    if (lower(p.name) == want) {
      hit = &p;
      ++n;
    }
  }
  if (n == 0) {
    error = "no person named " + name;
    return std::nullopt;
  }
  if (n > 1) {
    error = "more than one person named " + name;
    return std::nullopt;
  }
  return hit->id;
}

}  // namespace calypso
