#include "people_json.hpp"
#include "test_main.hpp"

using namespace calypso;

TEST(test_parse_people_basic) {
  const std::string j = R"([
    {"id":"a1","name":"Keanu \"KJ\" Lee","relationship":"brother","is_patient":false,
     "face_photo_url":"http://x/y","facts":["School together","Likes \"tea\""],"phone":"+1"},
    {"id":"b2","name":"Eric","relationship":null,"is_patient":true,
     "face_photo_url":null,"facts":[],"phone":null,"extra":{"k":[1,2,{"z":"}"}]}}
  ])";
  std::vector<PersonRef> p;
  CHECK(parse_people(j, p));
  CHECK_EQ(p.size(), 2u);
  CHECK_EQ(p[0].id, "a1");
  CHECK_EQ(p[0].name, "Keanu \"KJ\" Lee");
  CHECK(!p[0].is_patient);
  CHECK_EQ(p[1].id, "b2");
  CHECK_EQ(p[1].name, "Eric");
  CHECK(p[1].is_patient);
}

TEST(test_find_person_case_insensitive) {
  std::vector<PersonRef> p{{"1", "Eric", false}, {"2", "Keanu", false}};
  std::string err;
  auto id = find_person_id(p, "eric", err);
  CHECK(id.has_value());
  CHECK_EQ(*id, "1");
}

TEST(test_find_person_none_and_ambiguous) {
  std::vector<PersonRef> p{{"1", "Sam", false}, {"2", "sam", false}};
  std::string err;
  CHECK(!find_person_id(p, "Bob", err).has_value());
  CHECK_EQ(err, "no person named Bob");
  err.clear();
  CHECK(!find_person_id(p, "SAM", err).has_value());
  CHECK_EQ(err, "more than one person named SAM");
}

TEST(test_parse_people_invalid_json_false) {
  std::vector<PersonRef> p;
  CHECK(!parse_people("not json", p));
  CHECK(!parse_people("[{\"id\":\"a\",", p));
  CHECK(!parse_people("{\"id\":\"a\"}", p));
  CHECK(parse_people("[]", p));
  CHECK(p.empty());
}

int main() { return testing::run_all(); }
