// =====================================================================
// EXECUTIVE AI ASSISTANT - FRONTEND (STREAMING SSE + SQLITE MEMORY)
// =====================================================================

document.addEventListener("DOMContentLoaded", () => {
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");

  // Screenshot & Image Elements
  const imageUpload = document.getElementById("image-upload");
  const attachBtn = document.getElementById("attach-btn");
  const previewContainer = document.getElementById("image-preview-container");
  const previewImg = document.getElementById("image-preview");
  const previewName = document.getElementById("image-filename");
  const removeImgBtn = document.getElementById("remove-image-btn");

  let attachedImage = null; // { data: base64_str, mime_type: mime, filename: name }

  // Document Elements (Tier 3 Cloud Context)
  const docUpload = document.getElementById("doc-upload");
  const docAttachBtn = document.getElementById("doc-attach-btn");
  const docPreviewContainer = document.getElementById("doc-preview-container");
  const docFilename = document.getElementById("doc-filename");
  const removeDocBtn = document.getElementById("remove-doc-btn");

  let attachedDoc = null; // { file_name: "files/...", display_name: "...", redactions: 0 }

  // Voiceover & Audio Elements
  const micBtn = document.getElementById("mic-btn");
  const voiceIndicator = document.getElementById("voice-indicator");
  const voiceStatusText = document.getElementById("voice-status-text");
  const voiceToggleBtn = document.getElementById("voice-toggle-btn");

  let isRecording = false;
  let voiceOutputEnabled = false;
  let recognition = null;
  let speechSilenceTimer = null;

  // --- Font Size Adjustment Controls ---
  const body = document.body;
  const btnFontDec = document.getElementById("font-decrease");
  const btnFontReset = document.getElementById("font-reset");
  const btnFontInc = document.getElementById("font-increase");

  function setFontSize(sizeClass, activeBtn) {
    body.className = sizeClass;
    [btnFontDec, btnFontReset, btnFontInc].forEach(b => b.classList.remove("active"));
    activeBtn.classList.add("active");
  }

  btnFontDec.addEventListener("click", () => setFontSize("font-normal", btnFontDec));
  btnFontReset.addEventListener("click", () => setFontSize("font-large", btnFontReset));
  btnFontInc.addEventListener("click", () => setFontSize("font-xlarge", btnFontInc));

  // Default to large font for easy reading
  setFontSize("font-large", btnFontReset);

  // --- Image Attachment & Paste Handlers ---
  attachBtn.addEventListener("click", () => {
    imageUpload.click();
  });

  imageUpload.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file && file.type.startsWith("image/")) {
      processImageFile(file);
    }
  });

  // Direct Clipboard Paste (Ctrl+V) anywhere on page
  window.addEventListener("paste", (e) => {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (let index in items) {
      const item = items[index];
      if (item.kind === "file" && item.type.startsWith("image/")) {
        const blob = item.getAsFile();
        processImageFile(blob, "Pasted Screenshot");
        e.preventDefault();
        break;
      }
    }
  });

  function processImageFile(file, customName = null) {
    const reader = new FileReader();
    reader.onload = (event) => {
      attachedImage = {
        data: event.target.result,
        mime_type: file.type || "image/png",
        filename: customName || file.name || "Screenshot.png"
      };
      previewImg.src = attachedImage.data;
      previewName.textContent = attachedImage.filename;
      previewContainer.style.display = "flex";
      userInput.placeholder = "Add a question about this screenshot (or press Send to analyze)...";
      userInput.focus();
    };
    reader.readAsDataURL(file);
  }

  removeImgBtn.addEventListener("click", () => {
    clearAttachedImage();
  });

  function clearAttachedImage() {
    attachedImage = null;
    imageUpload.value = "";
    previewContainer.style.display = "none";
    previewImg.src = "";
    if (!attachedDoc) {
      userInput.placeholder = "Ask me anything, attach a document (📄), or paste a screenshot (Ctrl+V)...";
    }
  }

  // --- Document Attachment & Cloud Upload Handlers (Tier 3) ---
  docAttachBtn.addEventListener("click", () => {
    docUpload.click();
  });

  docUpload.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (file) {
      await uploadDocFile(file);
    }
  });

  async function uploadDocFile(file) {
    docPreviewContainer.style.display = "flex";
    docFilename.textContent = `Uploading ${file.name} to Tier 3 Cloud Context...`;
    
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/upload_doc", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");

      attachedDoc = {
        file_name: data.file_name,
        display_name: data.display_name,
        redactions: data.redactions_count
      };
      
      const scrubInfo = data.redactions_count > 0 ? ` (Scrubbed ${data.redactions_count} PII items)` : "";
      docFilename.textContent = `📄 ${data.display_name}${scrubInfo}`;
      userInput.placeholder = "Ask a question about this document (or press Send for full analysis)...";
      userInput.focus();
    } catch (err) {
      alert("Document upload error: " + err.message);
      clearAttachedDoc();
    }
  }

  removeDocBtn.addEventListener("click", () => {
    clearAttachedDoc();
  });

  function clearAttachedDoc() {
    attachedDoc = null;
    docUpload.value = "";
    docPreviewContainer.style.display = "none";
    docFilename.textContent = "Document attached";
    if (!attachedImage) {
      userInput.placeholder = "Ask me anything, speak (🎙️), attach a document (📄), or paste a screenshot (Ctrl+V)...";
    }
  }

  // =====================================================================
  // BEST-IN-CLASS SPEECH RECOGNITION (CONTINUOUS ACCUMULATION DICTATION)
  // =====================================================================
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const clearVoiceBtn = document.getElementById("clear-voice-btn");
  let baseInputText = "";
  let userManuallyStopped = true;

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      isRecording = true;
      if (micBtn) micBtn.classList.add("recording");
      if (voiceIndicator) voiceIndicator.style.display = "flex";
      if (voiceStatusText) voiceStatusText.textContent = "🎙️ Listening... (Speak freely • Pause as much as you like)";
      userInput.placeholder = "Listening... words will accumulate here...";
    };

    recognition.onresult = (event) => {
      let currentSessionFinal = "";
      let currentSessionInterim = "";

      // Accumulate across ALL results in this recognition session
      for (let i = 0; i < event.results.length; i++) {
        const item = event.results[i];
        if (item.isFinal) {
          currentSessionFinal += item[0].transcript + " ";
        } else {
          currentSessionInterim += item[0].transcript;
        }
      }

      const totalSessionSpeech = (currentSessionFinal + currentSessionInterim).trim();
      if (totalSessionSpeech) {
        const prefix = baseInputText ? baseInputText.trim() + " " : "";
        userInput.value = prefix + totalSessionSpeech;
      }
    };

    recognition.onerror = (event) => {
      console.warn("Speech recognition error:", event.error);
      if (event.error === "not-allowed") {
        alert("Microphone permission was denied. Please allow microphone access in your browser address bar.");
        userManuallyStopped = true;
        stopVoiceRecognition();
      }
    };

    recognition.onend = () => {
      // If user did NOT manually click Stop, keep listening across silence pauses
      if (!userManuallyStopped && isRecording) {
        baseInputText = userInput.value.trim();
        try {
          recognition.start();
        } catch (restartErr) {
          console.warn("Speech restart attempt:", restartErr);
        }
      } else {
        stopVoiceRecognition();
      }
    };

    if (micBtn) {
      micBtn.addEventListener("click", () => {
        if (isRecording) {
          // Explicitly STOP recording: DO NOT auto-submit! User reviews and sends manually.
          userManuallyStopped = true;
          baseInputText = userInput.value.trim();
          stopVoiceRecognition();
          userInput.focus();
        } else {
          userManuallyStopped = false;
          baseInputText = userInput.value.trim();
          startVoiceRecognition();
        }
      });
    }

    if (clearVoiceBtn) {
      clearVoiceBtn.addEventListener("click", () => {
        userInput.value = "";
        baseInputText = "";
        userManuallyStopped = true;
        stopVoiceRecognition();
        userInput.focus();
      });
    }

  } else {
    if (micBtn) {
      micBtn.title = "Speech recognition is supported in Edge and Chrome";
      micBtn.addEventListener("click", () => {
        alert("Voice recognition is supported in Microsoft Edge, Google Chrome, and modern Chromium browsers.");
      });
    }
  }

  function startVoiceRecognition() {
    if (!recognition) return;
    try {
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
      userManuallyStopped = false;
      recognition.start();
    } catch (e) {
      console.warn("Recognition start warning:", e);
    }
  }

  function stopVoiceRecognition() {
    isRecording = false;
    userManuallyStopped = true;
    if (micBtn) micBtn.classList.remove("recording");
    if (voiceIndicator) voiceIndicator.style.display = "none";
    if (userInput) {
      userInput.placeholder = "Ask me anything, speak (🎙️), attach a document (📄), or paste a screenshot (Ctrl+V)...";
    }
    if (recognition) {
      try { recognition.stop(); } catch (e) {}
    }
  }

  // =====================================================================
  // EXECUTIVE TEXT-TO-SPEECH (VOICE READOUT)
  // =====================================================================
  if (voiceToggleBtn) {
    voiceToggleBtn.addEventListener("click", () => {
      voiceOutputEnabled = !voiceOutputEnabled;
      if (voiceOutputEnabled) {
        voiceToggleBtn.classList.add("active");
        voiceToggleBtn.innerHTML = "<span>🔊</span> Voice: ON";
        speakText("Executive voice readout activated.");
      } else {
        voiceToggleBtn.classList.remove("active");
        voiceToggleBtn.innerHTML = "<span>🔇</span> Voice: OFF";
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
      }
    });
  }

  function speakText(rawText) {
    if (!voiceOutputEnabled || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();

    // Clean markdown before speaking
    const cleanText = rawText
      .replace(/<[^>]+>/g, " ")
      .replace(/[*_#`~|]/g, " ")
      .replace(/\[REDACTED_[A-Z_]+\]/g, "redacted")
      .replace(/\s+/g, " ")
      .trim();

    if (!cleanText) return;

    // Speak top summary (first 800 chars) for crisp executive briefings
    const utterance = new SpeechSynthesisUtterance(cleanText.slice(0, 800));
    utterance.rate = 1.05;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const naturalVoice = voices.find(v => v.lang.startsWith("en") && (v.name.includes("Natural") || v.name.includes("Google") || v.name.includes("David") || v.name.includes("Zira")));
    if (naturalVoice) utterance.voice = naturalVoice;

    window.speechSynthesis.speak(utterance);
  }

  // --- Markdown Formatter Helper ---
  function formatMarkdown(text) {
    let html = text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") // sanitize
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>") // bold
      .replace(/\*(.*?)\*/g, "<em>$1</em>") // italic
      .replace(/`(.*?)`/g, "<code style='background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px;font-family:JetBrains Mono;'>$1</code>")
      .replace(/^\* (.*$)/gim, "<li style='margin-left: 20px;'>$1</li>") // list item
      .replace(/^\- (.*$)/gim, "<li style='margin-left: 20px;'>$1</li>")
      .replace(/\n\n/g, "<br><br>")
      .replace(/\n/g, "<br>");
    return html;
  }

  // --- Create Real-Time Streaming Assistant Bubble ---
  function createStreamingAgentBubble() {
    const row = document.createElement("div");
    row.className = "message-row agent-row";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "💼";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble agent-bubble";

    const header = document.createElement("div");
    header.className = "message-header";
    const name = document.createElement("span");
    name.className = "sender-name";
    name.textContent = "Executive Assistant";
    const time = document.createElement("span");
    time.className = "timestamp";
    time.textContent = "Thinking...";
    header.appendChild(name);
    header.appendChild(time);
    bubble.appendChild(header);

    const toolsContainer = document.createElement("div");
    toolsContainer.className = "tools-container";
    bubble.appendChild(toolsContainer);

    const content = document.createElement("div");
    content.className = "message-content";
    content.innerHTML = `
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    `;
    bubble.appendChild(content);

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return {
      row,
      timeSpan: time,
      toolsContainer,
      contentDiv: content,
      appendTool: (tool, desc) => {
        const banner = document.createElement("div");
        banner.className = "tool-call-banner";
        banner.innerHTML = `
          <span>⚡</span>
          <span>Action Performed: <span class="tool-name-tag">${tool}()</span></span>
          <span style="color:var(--text-dim);font-size:0.85em;">&bull; ${desc}</span>
        `;
        toolsContainer.appendChild(banner);
        chatMessages.scrollTop = chatMessages.scrollHeight;
      },
      updateText: (markdownText) => {
        content.innerHTML = formatMarkdown(markdownText);
        chatMessages.scrollTop = chatMessages.scrollHeight;
      },
      finish: (latency) => {
        time.textContent = latency ? `${latency}s response time` : "Just now";
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    };
  }

  // --- Real-Time Streaming Chat Submit Handler ---
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    stopVoiceRecognition();

    const message = userInput.value.trim();
    if (!message && !attachedImage && !attachedDoc) return;

    // Capture payload copies for display
    const imgToSend = attachedImage;
    const docToSend = attachedDoc;
    let msgToSend = message;
    if (!msgToSend) {
      if (docToSend) msgToSend = `Please analyze and summarize the attached document: ${docToSend.display_name}.`;
      else if (imgToSend) msgToSend = "Please analyze this screenshot.";
    }

    // Append User Message Bubble with Thumbnail and/or Document Badge
    appendUserMessage(message, imgToSend ? imgToSend.data : null, docToSend ? docToSend.display_name : null);

    // Reset input fields immediately
    userInput.value = "";
    userInput.disabled = true;
    sendBtn.disabled = true;
    clearAttachedImage();
    clearAttachedDoc();

    // Create the streaming receiver bubble
    const streamingBubble = createStreamingAgentBubble();
    let fullResponse = "";
    let isFirstChunk = true;

    try {
      const payload = { message: msgToSend };
      if (imgToSend) {
        payload.image = {
          data: imgToSend.data,
          mime_type: imgToSend.mime_type
        };
      }
      if (docToSend) {
        payload.doc_ref = docToSend.file_name;
      }

      const res = await fetch("/api/chat_stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let hasError = false;
      let hasDone = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep last incomplete line

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const jsonStr = line.slice(6).trim();
            if (!jsonStr) continue;
            try {
              const ev = JSON.parse(jsonStr);
              if (ev.type === "tool") {
                streamingBubble.appendTool(ev.tool, ev.desc);
              } else if (ev.type === "chunk") {
                if (isFirstChunk) {
                  streamingBubble.contentDiv.innerHTML = "";
                  isFirstChunk = false;
                }
                fullResponse += ev.text;
                streamingBubble.updateText(fullResponse);
              } else if (ev.type === "done") {
                hasDone = true;
                streamingBubble.finish(ev.latency);
                if (fullResponse) {
                  speakText(fullResponse);
                }
              } else if (ev.type === "error") {
                hasError = true;
                streamingBubble.updateText(`⚠️ **Error:** ${ev.error}\n\n💡 *Try sending your message again.*`);
                streamingBubble.finish();
              }
            } catch (err) {
              console.warn("SSE parse error:", err);
            }
          }
        }
      }

      // Only show fallback if no text, no error, and no done event was received
      // This prevents overwriting real error messages with a misleading generic message
      if (!fullResponse && isFirstChunk && !hasError) {
        streamingBubble.updateText("⚠️ The assistant completed processing but returned no text. This may be a temporary model issue — please try again.");
        streamingBubble.finish();
      } else if (!hasDone && !hasError) {
        // Stream ended without a proper done/error event (connection dropped)
        streamingBubble.finish();
      }

    } catch (err) {
      streamingBubble.updateText(`⚠️ **Network Error:** Could not contact assistant server (${err.message}).`);
      streamingBubble.finish();
    } finally {
      userInput.disabled = false;
      sendBtn.disabled = false;
      userInput.focus();
    }
  });

  // --- Append User Message Bubble ---
  function appendUserMessage(text, imageSrc = null, docName = null) {
    const row = document.createElement("div");
    row.className = "message-row user-row";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "👤";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble user-bubble";

    const header = document.createElement("div");
    header.className = "message-header";
    const name = document.createElement("span");
    name.className = "sender-name";
    name.textContent = "You";
    const time = document.createElement("span");
    time.className = "timestamp";
    time.textContent = "Just now";
    header.appendChild(name);
    header.appendChild(time);
    bubble.appendChild(header);

    if (docName) {
      const docBadge = document.createElement("div");
      docBadge.className = "tool-call-banner";
      docBadge.style.margin = "0 0 10px 0";
      docBadge.style.background = "rgba(59, 130, 246, 0.25)";
      docBadge.style.border = "1px solid rgba(147, 197, 253, 0.4)";
      docBadge.innerHTML = `
        <span>📄</span>
        <span style="font-weight:600;color:#bfdbfe;">Attached Document: ${docName}</span>
        <span style="color:#93c5fd;font-size:0.82em;">(Tier 3 Cloud Context Active)</span>
      `;
      bubble.appendChild(docBadge);
    }

    if (imageSrc) {
      const imgEl = document.createElement("img");
      imgEl.src = imageSrc;
      imgEl.className = "chat-attached-image";
      imgEl.alt = "Attached Screenshot";
      bubble.appendChild(imgEl);
    }

    if (text) {
      const content = document.createElement("div");
      content.className = "message-content";
      content.innerHTML = formatMarkdown(text);
      bubble.appendChild(content);
    }

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
});
