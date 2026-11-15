#include "who_json.hpp"

#include <cstdio>
#include <sstream>

namespace calypso {
namespace {

std::string json_escape(const std::string& s) {
  std::string out;
  out.reserve(s.size() + 8);
  for (unsigned char c : s) {
    switch (c) {
      case '"':
        out += "\\\"";
        break;
      case '\\':
        out += "\\\\";
        break;
      case '\n':
        out += "\\n";
        break;
      case '\r':
        out += "\\r";
        break;
      case '\t':
        out += "\\t";
        break;
      default:
        if (c < 0x20) {
          char buf[8];
          std::snprintf(buf, sizeof(buf), "\\u%04x", c);
          out += buf;
        } else {
          out.push_back(static_cast<char>(c));
        }
    }
  }
  return out;
}

const char* status_str(WhoIsTalking::Status s) {
  switch (s) {
    case WhoIsTalking::Status::Identified:
      return "identified";
    case WhoIsTalking::Status::Uncertain:
      return "uncertain";
    case WhoIsTalking::Status::Unknown:
    default:
      return "unknown";
  }
}

}  // namespace

std::string who_to_json(const WhoIsTalking& who) {
  std::ostringstream o;
  o << "{\"status\":\"" << status_str(who.status) << "\""
    << ",\"person_id\":\"" << json_escape(who.person_id) << "\""
    << ",\"display_name\":\"" << json_escape(who.display_name) << "\""
    << ",\"relationship\":\"" << json_escape(who.relationship) << "\""
    << ",\"score\":";
  char score[32];
  std::snprintf(score, sizeof(score), "%.4f", static_cast<double>(who.score));
  o << score << "}";
  return o.str();
}

}  // namespace calypso
