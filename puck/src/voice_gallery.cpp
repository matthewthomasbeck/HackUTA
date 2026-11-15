#include "voice_gallery.hpp"

#include <cmath>

namespace calypso {

bool l2_normalize(std::vector<float>& v) {
  double sum = 0.0;
  for (float x : v) {
    sum += static_cast<double>(x) * static_cast<double>(x);
  }
  if (sum <= 1e-12) {
    return false;
  }
  const float inv = static_cast<float>(1.0 / std::sqrt(sum));
  for (float& x : v) {
    x *= inv;
  }
  return true;
}

float cosine_similarity(const std::vector<float>& a,
                        const std::vector<float>& b) {
  if (a.size() != b.size() || a.empty()) {
    return 0.f;
  }
  double dot = 0.0;
  for (std::size_t i = 0; i < a.size(); ++i) {
    dot += static_cast<double>(a[i]) * static_cast<double>(b[i]);
  }
  return static_cast<float>(dot);
}

void VoiceGallery::clear() {
  speakers_.clear();
}

bool VoiceGallery::empty() const {
  return speakers_.empty();
}

std::size_t VoiceGallery::size() const {
  return speakers_.size();
}

bool VoiceGallery::add(std::string name, std::vector<float> embedding) {
  if (name.empty() || !l2_normalize(embedding)) {
    return false;
  }
  for (auto& sp : speakers_) {
    if (sp.name == name) {
      sp.embedding = std::move(embedding);
      return true;
    }
  }
  speakers_.push_back(EnrolledSpeaker{std::move(name), std::move(embedding)});
  return true;
}

WhoIsTalking VoiceGallery::match(const std::vector<float>& embedding,
                                 float threshold) const {
  WhoIsTalking who;
  who.status = WhoIsTalking::Status::Unknown;
  if (speakers_.empty() || embedding.empty()) {
    return who;
  }

  std::vector<float> query = embedding;
  if (!l2_normalize(query)) {
    return who;
  }

  float best = -1.f;
  float second = -1.f;
  const EnrolledSpeaker* best_sp = nullptr;
  for (const auto& sp : speakers_) {
    const float s = cosine_similarity(query, sp.embedding);
    if (s > best) {
      second = best;
      best = s;
      best_sp = &sp;
    } else if (s > second) {
      second = s;
    }
  }

  who.score = best;
  if (!best_sp || best < threshold) {
    who.status = WhoIsTalking::Status::Uncertain;
    return who;
  }

  // Soft margin: if top-2 are too close, stay uncertain (anti-guess).
  if (second >= 0.f && (best - second) < 0.05f) {
    who.status = WhoIsTalking::Status::Uncertain;
    return who;
  }

  who.status = WhoIsTalking::Status::Identified;
  who.display_name = best_sp->name;
  who.person_id = best_sp->name;
  return who;
}

}  // namespace calypso
