const form = document.querySelector("#uploadForm");
const fileInput = document.querySelector("#videoFile");
const fileLabel = document.querySelector("#fileLabel");
const statusText = document.querySelector("#uploadStatus");
const uploadButton = document.querySelector("#uploadButton");
const dropZone = document.querySelector(".drop-zone");
let selectedFile = null;

function setSelectedFile(file) {
  if (!file) return;

  selectedFile = file;
  if (typeof DataTransfer !== "undefined") {
    const files = new DataTransfer();
    files.items.add(file);
    fileInput.files = files.files;
  }
  fileLabel.textContent = file.name;
  statusText.textContent = "";
}

function getMp4File(files) {
  return Array.from(files || []).find((file) => file.name.toLowerCase().endsWith(".mp4"));
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  selectedFile = file || null;
  fileLabel.textContent = file ? file.name : "맨발 360도 촬영 영상 선택";
});

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("drag-over");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("drag-over");
  });
});

dropZone.addEventListener("drop", (event) => {
  const file = getMp4File(event.dataTransfer.files);

  if (!file) {
    statusText.textContent = "드롭한 파일 중 MP4 파일을 찾을 수 없습니다.";
    return;
  }

  setSelectedFile(file);
  statusText.textContent = "MP4 파일이 선택되었습니다. 업로드 시작을 눌러 주세요.";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = selectedFile || fileInput.files[0];

  if (!file) {
    statusText.textContent = "먼저 MP4 영상을 선택해 주세요.";
    return;
  }

  if (!file.name.toLowerCase().endsWith(".mp4")) {
    statusText.textContent = "MP4 파일만 업로드할 수 있습니다.";
    return;
  }

  uploadButton.disabled = true;
  uploadButton.textContent = "업로드 중";
  statusText.textContent = "파일을 서버로 전송하고 있습니다.";

  const payload = new FormData();
  payload.append("file", file);

  try {
    const response = await fetch("/api/uploads", {
      method: "POST",
      body: payload,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "업로드에 실패했습니다.");
    }

    const data = await response.json();
    window.location.href = `/processing?upload_id=${data.id}`;
  } catch (error) {
    statusText.textContent = error.message;
    uploadButton.disabled = false;
    uploadButton.textContent = "업로드 시작";
  }
});
