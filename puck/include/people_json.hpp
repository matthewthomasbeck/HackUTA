#pragma once

#include <optional>
#include <string>
#include <vector>

namespace calypso {

struct PersonRef {
  std::string id;
  std::string name;
  bool is_patient = false;
};

// Parses GET /people (a JSON array of objects). Other fields are ignored,
// including nested arrays/objects and escaped strings.
bool parse_people(const std::string& json, std::vector<PersonRef>& out);

// Case-insensitive exact name match. Returns the id, or sets error to
// "no person named X" / "more than one person named X".
std::optional<std::string> find_person_id(const std::vector<PersonRef>& people,
                                          const std::string& name,
                                          std::string& error);

}  // namespace calypso
