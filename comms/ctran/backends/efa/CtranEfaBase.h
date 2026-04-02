// Copyright (c) Meta Platforms, Inc. and affiliates.

#ifndef CTRAN_EFA_BASE_H_
#define CTRAN_EFA_BASE_H_

#include <string>
#include "comms/utils/commSpecs.h"

// Maximum number of EFA rails (NICs) per rank.
// P5 instances can have up to 32 EFA NICs, but a single rank typically
// uses a subset based on GPU-NIC affinity.
#define CTRAN_MAX_EFA_RAILS_PER_RANK 4

struct CtranEfaRemoteAccessKey {
  std::array<uint64_t, CTRAN_MAX_EFA_RAILS_PER_RANK> rkeys{};
  int nKeys{0};

  std::string toString() const {
    std::string result;
    for (int i = 0; i < nKeys; i++) {
      if (i > 0) {
        result += ", ";
      }
      result += std::to_string(rkeys[i]);
    }
    return result;
  }
};

struct CtranEfaConfig {};

/**
 * Class of request to track progress of EFA operations.
 */
class CtranEfaRequest {
 public:
  CtranEfaRequest() {}
  ~CtranEfaRequest() {}

  void setRefCount(int refCount) {
    refCount_ = refCount;
  }

  inline commResult_t complete() {
    refCount_--;
    if (refCount_ == 0) {
      state_ = COMPLETE;
    }
    return commSuccess;
  }

  inline bool isComplete() const {
    return state_ == COMPLETE;
  }

  bool notify{false};

  void repost(int refCount) {
    refCount_ = refCount;
    state_ = INCOMPLETE;
  }

 private:
  enum {
    INCOMPLETE,
    COMPLETE,
  } state_{INCOMPLETE};
  int refCount_{1};
};

#endif
