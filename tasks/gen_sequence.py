#!/usr/bin/env python3
"""Generate EFA Backend Sequence Diagram as PNG — 3 pages, high readability."""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

C_SENDER = "#4A90D9"
C_RECEIVER = "#E8833A"
C_RDMA = "#CD5C5C"
C_NOTIFY = "#2E8B57"
C_PHASE = "#F3F3F3"
C_BARRIER = "#8B0000"

SENDER_X = 6.0
RECEIVER_X = 18.0
MID_X = (SENDER_X + RECEIVER_X) / 2


def setup_page(title, height=30):
    fig, ax = plt.subplots(1, 1, figsize=(24, height))
    ax.set_xlim(0, 24)
    ax.set_ylim(0, height)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.text(12, height - 0.5, title, ha="center", fontsize=18, fontweight="bold", color="#222")
    ax.plot([SENDER_X, SENDER_X], [height - 1.2, 0.3], color=C_SENDER, lw=2.5, ls="--", alpha=0.3)
    ax.plot([RECEIVER_X, RECEIVER_X], [height - 1.2, 0.3], color=C_RECEIVER, lw=2.5, ls="--", alpha=0.3)
    for x, label, color in [(SENDER_X, "Rank 0 (Sender)", C_SENDER), (RECEIVER_X, "Rank 1 (Receiver)", C_RECEIVER)]:
        box = mpatches.FancyBboxPatch((x - 2.5, height - 1.8), 5.0, 0.9, boxstyle="round,pad=0.12", facecolor=color, edgecolor="#333", lw=2)
        ax.add_patch(box)
        ax.text(x, height - 1.35, label, ha="center", va="center", fontsize=14, fontweight="bold", color="white")
    return fig, ax


def phase_bar(ax, y, height, label):
    box = mpatches.FancyBboxPatch((0.3, y - height), 23.4, height, boxstyle="round,pad=0.05", facecolor=C_PHASE, edgecolor="#BBB", lw=1, alpha=0.6)
    ax.add_patch(box)
    ax.text(0.7, y - 0.25, label, fontsize=14, fontweight="bold", color="#333", va="top")


def action(ax, x, y, text, color, side="left"):
    if side == "left":
        ax.text(x - 0.5, y, text, fontsize=10, color=color, va="center", ha="right",
                family="monospace", linespacing=1.4,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#bbb", alpha=0.95, lw=1.2))
    else:
        ax.text(x + 0.5, y, text, fontsize=10, color=color, va="center", ha="left",
                family="monospace", linespacing=1.4,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#bbb", alpha=0.95, lw=1.2))


def msg_arrow(ax, y, left_to_right=True, label="", color="#555", lw=2.5, dashed=False):
    if left_to_right:
        x1, x2 = SENDER_X + 0.2, RECEIVER_X - 0.2
    else:
        x1, x2 = RECEIVER_X - 0.2, SENDER_X + 0.2
    ls = "--" if dashed else "-"
    ax.annotate("", xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, ls=ls))
    if label:
        ax.text(MID_X, y + 0.3, label, ha="center", va="bottom", fontsize=10,
                color=color, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85))


def barrier_line(ax, y, label):
    """Draw a horizontal barrier/sync line across both lifelines."""
    ax.plot([SENDER_X - 0.5, RECEIVER_X + 0.5], [y, y], color=C_BARRIER, lw=2, ls="-.")
    ax.text(MID_X, y + 0.2, label, ha="center", va="bottom", fontsize=10,
            color=C_BARRIER, fontweight="bold", fontstyle="italic",
            bbox=dict(boxstyle="round,pad=0.12", facecolor="#FFF0F0", edgecolor=C_BARRIER, alpha=0.9, lw=1))


# ============================================================
# PAGE 1: Bootstrap, Registration, Control Exchange
# ============================================================
fig1, ax1 = setup_page("EFA Sequence: Bootstrap, Registration, Control Exchange", height=38)

Y = 35.5
phase_bar(ax1, Y, 11.0, "PHASE 1: Bootstrap & Initialization")

y = Y - 1.5
action(ax1, SENDER_X, y, "CtranEfaSingleton::getInstance()\n  fi_getinfo() -> discover EFA NICs\n  fi_fabric() / fi_domain()\n  Detect RDMA caps\n  Detect GDR support", C_SENDER, "left")
action(ax1, RECEIVER_X, y, "CtranEfaSingleton::getInstance()\n  fi_getinfo() -> discover EFA NICs\n  fi_fabric() / fi_domain()\n  Detect RDMA caps\n  Detect GDR support", C_RECEIVER, "right")

y -= 3.5
action(ax1, SENDER_X, y, "CtranEfa() per rail:\n  fi_endpoint(FI_EP_RDM)\n  fi_cq_open(FI_CQ_FORMAT_DATA)\n  fi_av_open(FI_AV_TABLE)\n  fi_ep_bind(cq, av)\n  fi_enable(ep)", C_SENDER, "left")
action(ax1, RECEIVER_X, y, "CtranEfa() per rail:\n  fi_endpoint(FI_EP_RDM)\n  fi_cq_open(FI_CQ_FORMAT_DATA)\n  fi_av_open(FI_AV_TABLE)\n  fi_ep_bind(cq, av)\n  fi_enable(ep)", C_RECEIVER, "right")

y -= 3.0
action(ax1, SENDER_X, y, "fi_getname(ep) -> local_addr", C_SENDER, "left")
action(ax1, RECEIVER_X, y, "fi_getname(ep) -> local_addr", C_RECEIVER, "right")

y -= 1.2
msg_arrow(ax1, y, True, "allgather(local_addrs) -- bootstrap address exchange", "#7B68EE")
y -= 0.7
msg_arrow(ax1, y, False, "", "#7B68EE", dashed=True)

y -= 1.2
action(ax1, SENDER_X, y, "fi_av_insert(peer_addrs)", C_SENDER, "left")
action(ax1, RECEIVER_X, y, "fi_av_insert(peer_addrs)", C_RECEIVER, "right")

Y = 24.0
phase_bar(ax1, Y, 5.5, "PHASE 2: Memory Registration")

y = Y - 1.5
action(ax1, SENDER_X, y, "mapper->regMem(sendbuf)\nctranEfa->regMem(buf, len, cudaDev)\n  per rail:\n  fi_mr_regattr(\n    iface  = FI_HMEM_CUDA\n    access = FI_SEND | FI_RECV |\n             FI_READ | FI_WRITE |\n             FI_REMOTE_READ |\n             FI_REMOTE_WRITE\n  ) -> mr_handle, rkey", C_SENDER, "left")
action(ax1, RECEIVER_X, y, "mapper->regMem(recvbuf)\nctranEfa->regMem(buf, len, cudaDev)\n  per rail:\n  fi_mr_regattr(\n    iface  = FI_HMEM_CUDA\n    access = FI_SEND | FI_RECV |\n             FI_READ | FI_WRITE |\n             FI_REMOTE_READ |\n             FI_REMOTE_WRITE\n  ) -> mr_handle, rkey", C_RECEIVER, "right")

Y = 18.0
phase_bar(ax1, Y, 8.5, "PHASE 3: Control Exchange (buffer metadata handshake)")

y = Y - 1.5
action(ax1, SENDER_X, y, "mapper->isendCtrl(sendbuf, hdl, peer=1)\n  exportMem() -> ControlMsg {\n    type: EFA_EXPORT_MEM\n    EfaDesc: {addr, rkeys[], nKeys}\n  }", C_SENDER, "left")

y -= 2.0
action(ax1, RECEIVER_X, y, "mapper->irecvCtrl(recvbuf, &key, peer=0)\n  irecvCtrlMsg()\n  fi_recv(ep, payload, size)", C_RECEIVER, "right")

y -= 1.5
msg_arrow(ax1, y, True, "fi_send(ep, &ctrl_msg, size, peer_fi_addr)", C_SENDER)

y -= 1.2
action(ax1, RECEIVER_X, y, "importMem(msg)\n  -> remoteAccessKey { addr, rkeys[] }", C_RECEIVER, "right")

y -= 1.2
msg_arrow(ax1, y, False, "fi_send(ep, &ctrl_msg, size, peer_fi_addr)", C_RECEIVER)

y -= 0.8
action(ax1, SENDER_X, y, "importMem(msg)\n  -> remoteAccessKey { addr, rkeys[] }", C_SENDER, "left")

fig1.tight_layout()
fig1.savefig("/home/ubuntu/torchcomms/tasks/efa_seq_part1.png", dpi=150, bbox_inches="tight", facecolor="white")
print("Saved efa_seq_part1.png")


# ============================================================
# PAGE 2: Data Transfer + Notification (SEQUENTIAL, not parallel)
# ============================================================
fig2, ax2 = setup_page("EFA Sequence: Data Transfer then Notification (strictly sequential)", height=34)

Y = 31.5
phase_bar(ax2, Y, 18.0, "PHASE 4: Data Transfer + Notification  (fi_writedata fires ONLY after all fi_write complete)")

# Step 1: iput call
y = Y - 1.5
action(ax2, SENDER_X, y, "mapper->iput(\n  sbuf, dbuf, len,\n  peer=1, notify=true)\nctranEfa->iput(...)", C_SENDER, "left")

# Step 2: stripe scheduling
y -= 2.2
action(ax2, SENDER_X, y, "Stripe Scheduler:\n  len < threshold\n    -> single rail (round-robin)\n  len > threshold\n    -> stripe across N rails\n       128-byte aligned chunks", "#555", "left")

# Step 3: RDMA writes
y -= 2.5
action(ax2, SENDER_X, y, "Per rail chunk:\nfi_write(ep,\n  local_buf + offset,\n  chunk_len,\n  local_mr_desc,\n  peer_fi_addr,\n  remote_addr + offset,\n  remote_rkey)", C_SENDER, "left")

msg_arrow(ax2, y, True, "RDMA WRITE over SRD  (zero-copy, OS bypass, GPUDirect)", C_RDMA, lw=4)

action(ax2, RECEIVER_X, y, "Data lands directly in\nGPU recvbuf via\nGPUDirect RDMA\n\n(no CPU copy)", C_RECEIVER, "right")

# Step 4: Poll for write completions
y -= 2.8
action(ax2, SENDER_X, y, "fi_cq_read(cq) per rail\n  -> comp_flags & FI_WRITE\n  req->refCount-- per chunk", C_SENDER, "left")

# BARRIER: all writes must complete before notification
y -= 1.5
barrier_line(ax2, y, "ALL fi_write completions received  (refCount == 0)")

# Step 5: NOW send notification
y -= 1.5
action(ax2, SENDER_X, y, "THEN: ctranEfa->notify(peer=1)\n  fi_writedata(ep,\n    NULL, 0,\n    imm = encode(\n      comm_id, seq_num),\n    peer_fi_addr,\n    remote_addr,\n    remote_rkey)", C_SENDER, "left")

msg_arrow(ax2, y, True, "fi_writedata()  [zero-byte WRITE + 32-bit immediate]", C_NOTIFY, lw=3.5)

# Step 6: Receiver gets notification
action(ax2, RECEIVER_X, y, "fi_cq_read(cq) ->\n  comp_flags & FI_REMOTE_WRITE\n  cqe.data = imm_data\n\ndecode(imm_data) ->\n  comm_id, seq_num\n  -> notify = true\n\n*** DATA IS NOW SAFE ***", C_RECEIVER, "right")

# Explanation note
y -= 3.5
note = mpatches.FancyBboxPatch((2.0, y - 0.6), 20, 1.5, boxstyle="round,pad=0.12", facecolor="#E8F5E9", edgecolor=C_NOTIFY, lw=2)
ax2.add_patch(note)
ax2.text(12, y + 0.15,
         "Key: fi_writedata is NOT a separate parallel operation.\n"
         "It is the tail of the data transfer: sender waits for ALL fi_write CQEs,\n"
         "THEN posts fi_writedata as the completion signal to the receiver.",
         ha="center", va="center", fontsize=11, color="#333", fontweight="bold")

fig2.tight_layout()
fig2.savefig("/home/ubuntu/torchcomms/tasks/efa_seq_part2.png", dpi=150, bbox_inches="tight", facecolor="white")
print("Saved efa_seq_part2.png")


# ============================================================
# PAGE 3: Progress, Cleanup, Fallback
# ============================================================
fig3, ax3 = setup_page("EFA Sequence: Progress, Cleanup & p4d Fallback", height=32)

Y = 29.5
phase_bar(ax3, Y, 6.5, "PHASE 5: Progress Engine (both ranks poll)")

y = Y - 2.0
action(ax3, SENDER_X, y, "ctranEfa->progress()\n  for each rail:\n    fi_cq_read(cq, &cqe, batch)\n\n    switch (cqe.flags):\n      FI_SEND  -> ctrl msg sent\n      FI_WRITE -> RDMA write done\n      FI_READ  -> RDMA read done\n\n    if FI_EAGAIN:\n      -> enqueue to pending ops", C_SENDER, "left")
action(ax3, RECEIVER_X, y, "ctranEfa->progress()\n  for each rail:\n    fi_cq_read(cq, &cqe, batch)\n\n    switch (cqe.flags):\n      FI_RECV         -> ctrl arrived\n      FI_REMOTE_WRITE -> data landed\n      FI_REMOTE_WRITE\n        + imm_data   -> notification\n\n    if FI_EAGAIN:\n      -> enqueue to pending ops", C_RECEIVER, "right")

Y = 22.5
phase_bar(ax3, Y, 3.0, "PHASE 6: Cleanup")

y = Y - 1.3
action(ax3, SENDER_X, y, "mapper->deregMem(hdl)\nctranEfa->deregMem(efaRegElem)\n  per rail: fi_close(mr)", C_SENDER, "left")
action(ax3, RECEIVER_X, y, "mapper->deregMem(hdl)\nctranEfa->deregMem(efaRegElem)\n  per rail: fi_close(mr)", C_RECEIVER, "right")

# Fallback
Y = 19.0
ax3.text(12, Y, "FALLBACK:  p4d Instance (No RDMA Write)", ha="center", fontsize=16, fontweight="bold", color="#8B0000")

fb_box = mpatches.FancyBboxPatch((0.8, 1.0), 22.4, Y - 1.5, boxstyle="round,pad=0.15", facecolor="#FFF5F5", edgecolor="#CD5C5C", lw=2)
ax3.add_patch(fb_box)

ax3.text(12, Y - 0.8, "Singleton detects:  RDMA Write NOT supported  (Nitro v3 -- p4d / p4de)",
         ha="center", fontsize=11, color="#8B0000", fontstyle="italic")

ax3.plot([SENDER_X, SENDER_X], [Y - 1.5, 1.5], color=C_SENDER, lw=2, ls=":", alpha=0.3)
ax3.plot([RECEIVER_X, RECEIVER_X], [Y - 1.5, 1.5], color=C_RECEIVER, lw=2, ls=":", alpha=0.3)

y = Y - 2.5
action(ax3, SENDER_X, y, "ctranEfa->iget(sbuf, dbuf, len)\n  fi_read(ep,\n    local_buf, len,\n    local_mr_desc,\n    peer_fi_addr,\n    remote_addr,\n    remote_rkey)", C_SENDER, "left")
action(ax3, RECEIVER_X, y, "(remote MR\n previously\n exported)", C_RECEIVER, "right")

y -= 2.2
msg_arrow(ax3, y, True, "RDMA READ request (all EFA instances)", C_RDMA, lw=3)
y -= 0.8
msg_arrow(ax3, y, False, "RDMA READ response (data returned)", C_RDMA, lw=3, dashed=True)

y -= 0.8
action(ax3, SENDER_X, y, "Data arrives in local GPU buf", "#666", "left")

y -= 1.5
barrier_line(ax3, y, "fi_read CQ completion received")

y -= 1.5
ax3.text(12, y + 0.5, "THEN: Notification via explicit fi_send / fi_recv",
         ha="center", fontsize=12, color="#8B0000", fontweight="bold")

y -= 1.0
action(ax3, SENDER_X, y, "ctranEfa->notify(peer=1)\n  fi_send(ep,\n    &notify_msg, size,\n    NULL, peer_fi_addr)", C_SENDER, "left")

msg_arrow(ax3, y, True, "fi_send  (tagged notification)", C_NOTIFY, lw=3)

action(ax3, RECEIVER_X, y, "fi_recv(ep,\n  &notify_msg, size)\n  -> CQ: FI_RECV\n  decode -> notify = true", C_RECEIVER, "right")

y -= 2.5
note = mpatches.FancyBboxPatch((2.0, y - 0.5), 20, 1.2, boxstyle="round,pad=0.12", facecolor="#FFFDE7", edgecolor="#F9A825", lw=2)
ax3.add_patch(note)
ax3.text(12, y + 0.1,
         "Instance Matrix:   p4d/p4de (Nitro v3) = RDMA Read only\n"
         "p5/p5e/p5en/p6 (Nitro v4+) = RDMA Read + Write     |     "
         "Detection: EFADV_DEVICE_ATTR_CAPS_RDMA_WRITE at init",
         ha="center", va="center", fontsize=10, color="#333")

fig3.tight_layout()
fig3.savefig("/home/ubuntu/torchcomms/tasks/efa_seq_part3.png", dpi=150, bbox_inches="tight", facecolor="white")
print("Saved efa_seq_part3.png")
