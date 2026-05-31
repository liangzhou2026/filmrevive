const API_BASE_URL =
  window.FILMREVIVE_API_BASE_URL ||
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8001"
    : "https://api.filmrevive.app");
const { useEffect, useState } = React;

const TEXT = {
  title: "\u624b\u673a\u8d1f\u7247\u8f6c\u6b63\u7247 Demo",
  upload: "\u4e0a\u4f20\u8d1f\u7247",
  process: "\u4e00\u952e\u53bb\u8272\u7f69",
  processing: "\u5904\u7406\u4e2d...",
  stop: "\u505c\u6b62\u5904\u7406",
  stopped: "\u5df2\u505c\u6b62\u5904\u7406\u3002",
  download: "\u4e0b\u8f7d\u6b63\u7247",
  processFailed: "\u56fe\u7247\u5904\u7406\u5931\u8d25\u3002",
  processFailedRetry: "\u56fe\u7247\u5904\u7406\u5931\u8d25\uff0c\u8bf7\u6362\u4e00\u5f20\u7167\u7247\u518d\u8bd5\u3002",
  colorCastTitle: "\u4e00\u952e\u53bb\u8272\u7f69",
  oneClickColorCast: "\u53bb\u6a59\u8272\u7f69\u3001RGB \u8865\u507f\u3001\u81ea\u52a8\u8272\u9636",
  repairTitle: "\u4fee\u590d\u9009\u9879",
  denoise: "\u53bb\u566a\u70b9",
  before: "Before \u539f\u56fe\u8d1f\u7247",
  after: "After \u8f6c\u6362\u6b63\u7247",
  beforeEmpty: "\u4e0a\u4f20\u4e00\u5f20\u624b\u673a\u62cd\u6444\u7684\u5f69\u8272\u8d1f\u7247\u7167\u7247",
  afterEmpty: "\u70b9\u51fb\u81ea\u52a8\u8f6c\u6b63\u7247\u540e\u663e\u793a\u7ed3\u679c",
};

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [originalUrl, setOriginalUrl] = useState("");
  const [processedUrl, setProcessedUrl] = useState("");
  const [previewAspect, setPreviewAspect] = useState("3 / 4");
  const [oneClickColorCast, setOneClickColorCast] = useState(true);
  const [denoise, setDenoise] = useState(false);
  const [state, setState] = useState("idle");
  const [error, setError] = useState("");
  const [abortController, setAbortController] = useState(null);

  useEffect(() => {
    return () => {
      if (originalUrl) URL.revokeObjectURL(originalUrl);
      if (processedUrl) URL.revokeObjectURL(processedUrl);
    };
  }, [originalUrl, processedUrl]);

  function handleFileChange(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (originalUrl) URL.revokeObjectURL(originalUrl);
    if (processedUrl) URL.revokeObjectURL(processedUrl);

    const nextOriginalUrl = URL.createObjectURL(file);
    setSelectedFile(file);
    setOriginalUrl(nextOriginalUrl);
    setProcessedUrl("");
    setPreviewAspect("3 / 4");
    setState("idle");
    setError("");

    const probe = new Image();
    probe.onload = () => {
      if (probe.naturalWidth && probe.naturalHeight) {
        setPreviewAspect(`${probe.naturalWidth} / ${probe.naturalHeight}`);
      }
    };
    probe.src = nextOriginalUrl;
  }

  async function processImage() {
    if (!selectedFile) return;

    setState("processing");
    setError("");
    const controller = new AbortController();
    setAbortController(controller);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("one_click_color_cast", String(oneClickColorCast));
    formData.append("denoise", String(denoise));

    try {
      const response = await fetch(`${API_BASE_URL}/api/convert`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || TEXT.processFailedRetry);
      }

      const blob = await response.blob();
      if (processedUrl) URL.revokeObjectURL(processedUrl);
      setProcessedUrl(URL.createObjectURL(blob));
      setState("done");
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setState("idle");
        setError(TEXT.stopped);
        return;
      }
      setState("error");
      setError(err instanceof Error ? err.message : TEXT.processFailed);
    } finally {
      setAbortController(null);
    }
  }

  function stopProcessing() {
    if (abortController) {
      abortController.abort();
    }
  }

  const canProcess = Boolean(selectedFile) && state !== "processing";

  return h(
    "main",
    { className: "app-shell" },
    h(
      "section",
      { className: "workspace" },
      h(
        "header",
        { className: "topbar" },
        h("div", null, h("p", { className: "eyebrow" }, "FilmRevive MVP"), h("h1", null, TEXT.title)),
        h(
          "label",
          { className: "upload-button" },
          h("span", { "aria-hidden": "true" }, "+"),
          h("span", null, TEXT.upload),
          h("input", {
            accept: ".jpg,.jpeg,.png,.webp,.bmp,.tif,.tiff,image/jpeg,image/png,image/webp,image/bmp,image/tiff",
            type: "file",
            onChange: handleFileChange,
          }),
        ),
      ),
      h(ControlPanel, {
        denoise,
        oneClickColorCast,
        setDenoise,
        setOneClickColorCast,
        state,
      }),
      h(
        "div",
        { className: "action-row" },
        h(
          "button",
          { className: "primary-button", disabled: !canProcess, onClick: processImage },
          h("span", { className: state === "processing" ? "button-icon spin" : "button-icon", "aria-hidden": "true" }, state === "processing" ? "o" : "*"),
          h("span", null, state === "processing" ? TEXT.processing : TEXT.process),
        ),
        state === "processing" &&
          h(
            "button",
            { className: "danger-button", onClick: stopProcessing, type: "button" },
            h("span", { "aria-hidden": "true" }, "x"),
            h("span", null, TEXT.stop),
          ),
        processedUrl &&
          h(
            "a",
            { className: "secondary-button", download: "filmrevive-positive.jpg", href: processedUrl },
            h("span", { "aria-hidden": "true" }, "v"),
            h("span", null, TEXT.download),
          ),
      ),
      error && h("p", { className: "error-message" }, error),
      h(
        "section",
        { className: "compare-grid", "aria-label": "before after image comparison" },
        h(ImagePanel, {
          label: TEXT.before,
          imageUrl: originalUrl,
          emptyText: TEXT.beforeEmpty,
          previewAspect,
        }),
        h(ImagePanel, {
          label: TEXT.after,
          imageUrl: processedUrl,
          emptyText: TEXT.afterEmpty,
          previewAspect,
        }),
      ),
    ),
  );
}

function ControlPanel({
  denoise,
  setDenoise,
  setOneClickColorCast,
  oneClickColorCast,
  state,
}) {
  return h(
    "section",
    { className: "controls-panel", "aria-label": "film and repair controls" },
    h("div", { className: "control-title" }, TEXT.colorCastTitle),
    h(
      "div",
      { className: "repair-row" },
      h(ToggleButton, {
        active: oneClickColorCast,
        disabled: state === "processing",
        label: TEXT.oneClickColorCast,
        onClick: () => setOneClickColorCast(!oneClickColorCast),
      }),
    ),
    h("div", { className: "control-title repair-title" }, TEXT.repairTitle),
    h(
      "div",
      { className: "repair-row" },
      h(ToggleButton, {
        active: denoise,
        disabled: state === "processing",
        label: TEXT.denoise,
        onClick: () => setDenoise(!denoise),
      }),
    ),
  );
}

function ToggleButton({ active, disabled, label, onClick }) {
  return h(
    "button",
    {
      className: active ? "toggle-button active" : "toggle-button",
      disabled,
      onClick,
      type: "button",
    },
    h("span", { "aria-hidden": "true" }, active ? "✓" : ""),
    h("span", null, label),
  );
}

function ImagePanel({ label, imageUrl, emptyText, previewAspect }) {
  return h(
    "article",
    { className: "image-panel" },
    h("div", { className: "panel-header" }, label),
    h(
      "div",
      { className: "image-stage", style: { "--preview-aspect": previewAspect } },
      imageUrl ? h("img", { alt: label, src: imageUrl }) : h("span", null, emptyText),
    ),
  );
}

const h = React.createElement;

ReactDOM.createRoot(document.getElementById("root")).render(h(React.StrictMode, null, h(App)));

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
