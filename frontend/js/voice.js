// Push-to-talk: hold the floating mic button, speak, release. Lives outside
// the router's #view (wired up once from app.js at startup, not per-page),
// so it's available no matter what screen is showing.
//
// Recording -> POST /voice/command-audio (multipart) -> transcript + reply
// + any tool calls the LLM made. STT runs on the self-hosted whisper.cpp
// server (kitchen_ai_spec.md §12), never a cloud API. The reply is read
// back with the browser's built-in speech synthesis -- on-device, so
// unlike STT this carries none of the "leaves the house" privacy tradeoff.

import { el, toast, errorMessage } from "./util.js";

const MAX_RECORDING_MS = 20000; // safety cap so a stuck button can't record forever

function speak(text) {
  try {
    if (!window.speechSynthesis || !text) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
  } catch {
    /* TTS is a nice-to-have -- never let it block anything */
  }
}

export function initVoice() {
  const fab = document.getElementById("voice-fab");
  const panel = document.getElementById("voice-panel");
  if (!fab || !panel) return;

  let mediaRecorder = null;
  let stream = null;
  let chunks = [];
  let recording = false;
  let safetyTimer = null;

  function setFabState(state) {
    fab.classList.remove("recording", "processing");
    if (state) fab.classList.add(state);
  }

  function showPanel(contentBuilder) {
    panel.innerHTML = "";
    contentBuilder(panel);
    panel.hidden = false;
  }

  function hidePanel() {
    panel.hidden = true;
    panel.innerHTML = "";
  }

  async function startRecording() {
    if (recording) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      toast("Voice isn't available in this browser/context (needs HTTPS or localhost for microphone access).", { error: true });
      return;
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      toast("Microphone permission denied.", { error: true });
      return;
    }

    chunks = [];
    try {
      mediaRecorder = new MediaRecorder(stream);
    } catch {
      toast("Recording isn't supported in this browser.", { error: true });
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
      return;
    }

    mediaRecorder.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size) chunks.push(e.data);
    });
    mediaRecorder.addEventListener("stop", handleStop);

    mediaRecorder.start();
    recording = true;
    setFabState("recording");
    hidePanel();
    safetyTimer = setTimeout(stopRecording, MAX_RECORDING_MS);
  }

  function stopRecording() {
    if (!recording) return;
    recording = false;
    clearTimeout(safetyTimer);
    setFabState("processing");
    try {
      mediaRecorder.stop();
    } catch {
      /* already stopped */
    }
    stream?.getTracks().forEach((t) => t.stop());
    stream = null;
  }

  async function handleStop() {
    const blob = new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" });
    if (!blob.size) {
      setFabState(null);
      return;
    }

    showPanel((p) => {
      p.appendChild(el("div", { class: "voice-status" }, "Thinking…"));
    });

    try {
      const ext = (blob.type.split("/")[1] || "webm").split(";")[0];
      const form = new FormData();
      form.append("file", blob, `command.${ext}`);
      const res = await fetch("/voice/command-audio", { method: "POST", body: form });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw { detail: data?.detail };
      renderResult(data);
    } catch (err) {
      showPanel((p) => {
        p.appendChild(el("div", { class: "voice-status error" }, errorMessage(err)));
        p.appendChild(el("button", { class: "btn ghost small", onclick: hidePanel }, "Dismiss"));
      });
    } finally {
      setFabState(null);
    }
  }

  function renderResult(data) {
    showPanel((p) => {
      if (data.transcript) p.appendChild(el("div", { class: "voice-heard" }, `“${data.transcript}”`));
      p.appendChild(el("div", { class: "voice-reply" }, data.reply));
      p.appendChild(el("button", { class: "btn ghost small", onclick: hidePanel }, "Dismiss"));
    });
    speak(data.reply);
  }

  fab.addEventListener("mousedown", startRecording);
  fab.addEventListener("mouseup", stopRecording);
  fab.addEventListener("mouseleave", stopRecording);
  fab.addEventListener("touchstart", (e) => {
    e.preventDefault();
    startRecording();
  }, { passive: false });
  fab.addEventListener("touchend", (e) => {
    e.preventDefault();
    stopRecording();
  });
  fab.addEventListener("touchcancel", stopRecording);
  window.addEventListener("blur", stopRecording);
}
