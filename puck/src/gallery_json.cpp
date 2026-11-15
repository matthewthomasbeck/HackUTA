#include "gallery_json.hpp"

#include <cctype>
#include <cstdlib>
#include <string_view>

namespace calypso {
namespace {

void skip_ws(std::string_view s, std::size_t& i) {
  while (i < s.size() && std::isspace(static_cast<unsigned char>(s[i]))) {
    ++i;
  }
}

bool consume(std::string_view s, std::size_t& i, char c) {
  skip_ws(s, i);
  if (i >= s.size() || s[i] != c) {
    return false;
  }
  ++i;
  return true;
}

bool parse_string(std::string_view s, std::size_t& i, std::string& out) {
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
    if (c == '\\' && i < s.size()) {
      const char e = s[i++];
      switch (e) {
        case '"':
        case '\\':
        case '/':
          out.push_back(e);
          break;
        case 'n':
          out.push_back('\n');
          break;
        case 'r':
          out.push_back('\r');
          break;
        case 't':
          out.push_back('\t');
          break;
        case 'u':
          // Skip 4 hex digits; keep a '?' placeholder (names are ASCII for MVP).
          for (int k = 0; k < 4 && i < s.size(); ++k) {
            ++i;
          }
          out.push_back('?');
          break;
        default:
          out.push_back(e);
          break;
      }
      continue;
    }
    out.push_back(c);
  }
  return false;
}

bool parse_bool(std::string_view s, std::size_t& i, bool& out) {
  skip_ws(s, i);
  if (s.substr(i, 4) == "true") {
    i += 4;
    out = true;
    return true;
  }
  if (s.substr(i, 5) == "false") {
    i += 5;
    out = false;
    return true;
  }
  return false;
}

bool parse_null(std::string_view s, std::size_t& i) {
  skip_ws(s, i);
  if (s.substr(i, 4) == "null") {
    i += 4;
    return true;
  }
  return false;
}

bool parse_string_or_null(std::string_view s, std::size_t& i, std::string& out) {
  skip_ws(s, i);
  if (parse_null(s, i)) {
    out.clear();
    return true;
  }
  return parse_string(s, i, out);
}

bool parse_number(std::string_view s, std::size_t& i, float& out) {
  skip_ws(s, i);
  if (i >= s.size()) {
    return false;
  }
  char* end = nullptr;
  const std::string tmp(s.substr(i));
  const float v = std::strtof(tmp.c_str(), &end);
  if (end == tmp.c_str()) {
    return false;
  }
  i += static_cast<std::size_t>(end - tmp.c_str());
  out = v;
  return true;
}

bool parse_float_array(std::string_view s, std::size_t& i,
                       std::vector<float>& out) {
  out.clear();
  if (!consume(s, i, '[')) {
    return false;
  }
  skip_ws(s, i);
  if (i < s.size() && s[i] == ']') {
    ++i;
    return true;
  }
  while (i < s.size()) {
    float v = 0.f;
    if (!parse_number(s, i, v)) {
      return false;
    }
    out.push_back(v);
    skip_ws(s, i);
    if (i < s.size() && s[i] == ',') {
      ++i;
      continue;
    }
    if (i < s.size() && s[i] == ']') {
      ++i;
      return true;
    }
    return false;
  }
  return false;
}

bool parse_speaker(std::string_view s, std::size_t& i, EnrolledSpeaker& sp) {
  sp = {};
  if (!consume(s, i, '{')) {
    return false;
  }
  skip_ws(s, i);
  if (i < s.size() && s[i] == '}') {
    ++i;
    return !sp.person_id.empty() && !sp.embedding.empty();
  }
  while (i < s.size()) {
    std::string key;
    if (!parse_string(s, i, key) || !consume(s, i, ':')) {
      return false;
    }
    if (key == "person_id") {
      if (!parse_string(s, i, sp.person_id)) {
        return false;
      }
    } else if (key == "display_name") {
      if (!parse_string_or_null(s, i, sp.display_name)) {
        return false;
      }
    } else if (key == "relationship") {
      if (!parse_string_or_null(s, i, sp.relationship)) {
        return false;
      }
    } else if (key == "is_patient") {
      if (!parse_bool(s, i, sp.is_patient)) {
        return false;
      }
    } else if (key == "embedding") {
      if (!parse_float_array(s, i, sp.embedding)) {
        return false;
      }
    } else {
      // Skip unknown value: string, number, bool, null, array, object — lightweight.
      skip_ws(s, i);
      if (i < s.size() && s[i] == '"') {
        std::string junk;
        if (!parse_string(s, i, junk)) {
          return false;
        }
      } else if (parse_null(s, i) || (i + 4 <= s.size() && s.substr(i, 4) == "true") ||
                 (i + 5 <= s.size() && s.substr(i, 5) == "false")) {
        if (s.substr(i, 4) == "true") {
          i += 4;
        } else if (s.substr(i, 5) == "false") {
          i += 5;
        }
      } else if (i < s.size() && (s[i] == '-' || std::isdigit(static_cast<unsigned char>(s[i])))) {
        float junk = 0.f;
        if (!parse_number(s, i, junk)) {
          return false;
        }
      } else if (i < s.size() && s[i] == '[') {
        std::vector<float> junk;
        if (!parse_float_array(s, i, junk)) {
          return false;
        }
      } else {
        return false;
      }
    }
    skip_ws(s, i);
    if (i < s.size() && s[i] == ',') {
      ++i;
      continue;
    }
    if (i < s.size() && s[i] == '}') {
      ++i;
      return !sp.person_id.empty() && !sp.embedding.empty();
    }
    return false;
  }
  return false;
}

}  // namespace

bool parse_puck_gallery(const std::string& json,
                        std::vector<EnrolledSpeaker>& out) {
  out.clear();
  const std::string_view s(json);
  std::size_t i = 0;
  if (!consume(s, i, '{')) {
    return false;
  }
  // Find "people" key (order-tolerant for a single top-level object).
  bool found_people = false;
  skip_ws(s, i);
  if (i < s.size() && s[i] == '}') {
    return true;  // empty object → empty gallery
  }
  while (i < s.size()) {
    std::string key;
    if (!parse_string(s, i, key) || !consume(s, i, ':')) {
      return false;
    }
    if (key == "people") {
      found_people = true;
      if (!consume(s, i, '[')) {
        return false;
      }
      skip_ws(s, i);
      if (i < s.size() && s[i] == ']') {
        ++i;
      } else {
        while (i < s.size()) {
          EnrolledSpeaker sp;
          if (!parse_speaker(s, i, sp)) {
            return false;
          }
          out.push_back(std::move(sp));
          skip_ws(s, i);
          if (i < s.size() && s[i] == ',') {
            ++i;
            continue;
          }
          if (i < s.size() && s[i] == ']') {
            ++i;
            break;
          }
          return false;
        }
      }
    } else {
      // Skip other top-level values we don't care about.
      skip_ws(s, i);
      if (i < s.size() && s[i] == '"') {
        std::string junk;
        if (!parse_string(s, i, junk)) {
          return false;
        }
      } else if (i < s.size() && s[i] == '[') {
        // Skip array of objects by scanning brackets — only used if unknown key.
        int depth = 0;
        do {
          if (s[i] == '[') {
            ++depth;
          } else if (s[i] == ']') {
            --depth;
          }
          ++i;
        } while (i < s.size() && depth > 0);
      } else if (i < s.size() && s[i] == '{') {
        int depth = 0;
        do {
          if (s[i] == '{') {
            ++depth;
          } else if (s[i] == '}') {
            --depth;
          }
          ++i;
        } while (i < s.size() && depth > 0);
      } else if (parse_null(s, i)) {
        // ok
      } else {
        float junk = 0.f;
        bool bj = false;
        if (!(parse_bool(s, i, bj) || parse_number(s, i, junk))) {
          return false;
        }
      }
    }
    skip_ws(s, i);
    if (i < s.size() && s[i] == ',') {
      ++i;
      continue;
    }
    if (i < s.size() && s[i] == '}') {
      return found_people;
    }
    return false;
  }
  return found_people;
}

}  // namespace calypso
