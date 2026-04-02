// Copyright (c) Meta Platforms, Inc. and affiliates.

#pragma once

#include <unordered_set>
#include "comms/ctran/CtranComm.h"
#include "comms/ctran/backends/CtranCtrl.h"
#include "comms/ctran/backends/mock/CtranEfaBaseMock.h"

class CtranEfa {
 public:
  CtranEfa(CtranComm* comm, CtranCtrlManager* ctrlMgr) {}
  ~CtranEfa() {}

  commResult_t preConnect(const std::unordered_set<int>& peerRanks) {
    return commInvalidUsage;
  }

  static commResult_t
  regMem(const void* buf, const size_t len, const int cudaDev, void** handle) {
    return commInvalidUsage;
  }

  static commResult_t deregMem(void* handle) {
    return commInvalidUsage;
  }

  static commResult_t
  exportMem(const void* buf, void* efaRegElem, ControlMsg& msg) {
    return commInvalidUsage;
  }

  static commResult_t importMem(
      void** buf,
      CtranEfaRemoteAccessKey* key,
      const ControlMsg& msg) {
    return commInvalidUsage;
  }

  template <typename PerfConfig = DefaultPerfCollConfig>
  commResult_t iput(
      const void* sbuf,
      void* dbuf,
      std::size_t len,
      int peerRank,
      void* efaRegElem,
      CtranEfaRemoteAccessKey remoteAccessKey,
      bool notify,
      CtranEfaConfig* config,
      CtranEfaRequest* req) {
    return commInvalidUsage;
  }

  template <typename PerfConfig = DefaultPerfCollConfig>
  commResult_t iget(
      const void* sbuf,
      void* dbuf,
      std::size_t len,
      int peerRank,
      void* efaRegElem,
      CtranEfaRemoteAccessKey remoteAccessKey,
      CtranEfaConfig* config,
      CtranEfaRequest* req) {
    return commInvalidUsage;
  }

  template <typename PerfConfig = DefaultPerfCollConfig>
  commResult_t isendCtrlMsg(
      int type,
      const void* payload,
      size_t size,
      int peerRank,
      CtranEfaRequest& req) {
    return commInvalidUsage;
  }

  template <typename PerfConfig = DefaultPerfCollConfig>
  commResult_t
  irecvCtrlMsg(void* payload, size_t size, int peerRank, CtranEfaRequest& req) {
    return commInvalidUsage;
  }

  commResult_t notify(int peerRank, CtranEfaRequest* req) {
    return commInvalidUsage;
  }

  template <typename PerfConfig = DefaultPerfCollConfig>
  commResult_t checkNotify(int peerRank, bool* notify) {
    return commInvalidUsage;
  }

  template <typename PerfConfig = DefaultPerfCollConfig>
  commResult_t waitNotify(int peerRank, int notifyCnt = 1) {
    return commInvalidUsage;
  }

  template <typename PerfConfig = DefaultPerfCollConfig>
  commResult_t progress() {
    return commInvalidUsage;
  }

  commResult_t regCtrlCb(std::unique_ptr<CtranCtrlManager>& ctrlMgr) {
    return commInvalidUsage;
  }
};
