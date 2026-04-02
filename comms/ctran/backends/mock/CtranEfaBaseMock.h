// Copyright (c) Meta Platforms, Inc. and affiliates.

#pragma once

#include <string>
#include "comms/utils/commSpecs.h"

#define CTRAN_MAX_EFA_RAILS_PER_RANK 4

struct CtranEfaRemoteAccessKey {
  std::array<uint64_t, CTRAN_MAX_EFA_RAILS_PER_RANK> rkeys{};
  int nKeys{0};

  std::string toString() const {
    return "";
  }
};

struct CtranEfaConfig {};

class CtranEfaRequest {
 public:
  explicit CtranEfaRequest() {}

  bool isComplete() {
    return false;
  }

  void complete() {}

  bool notify{false};
};
