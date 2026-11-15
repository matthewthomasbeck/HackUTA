#pragma once

#include "types.hpp"

#include <string>
#include <vector>

namespace calypso {

// Local enrolled speakers for offline emergency ID.
// Each entry: backend person_id + display fields + L2-normalized embedding
// (titanet-small → 192-d). Cloud sync replace-alls this list.
struct EnrolledSpeaker {
  std::string person_id;
  std::string display_name;
  std::string relationship;
  bool is_patient = false;
  std::vector<float> embedding;  // unit vector
};

class VoiceGallery {
 public:
  void clear();
  bool empty() const;
  std::size_t size() const;

  // Add or replace by person_id (falls back to display_name if id empty).
  // Embedding is L2-normalized in place.
  bool add(EnrolledSpeaker speaker);

  // Convenience for local WAV bootstrap (person_id = name).
  bool add(std::string name, std::vector<float> embedding);

  // Cosine vs gallery. Best score ≥ threshold → Identified; else Uncertain.
  WhoIsTalking match(const std::vector<float>& embedding, float threshold) const;

 private:
  std::vector<EnrolledSpeaker> speakers_;
};

// L2-normalize; returns false if vector is empty / near-zero.
bool l2_normalize(std::vector<float>& v);

// Cosine similarity of two unit (or raw) vectors. Returns 0 if dims mismatch.
float cosine_similarity(const std::vector<float>& a, const std::vector<float>& b);

}  // namespace calypso
