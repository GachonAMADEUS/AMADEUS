const params = new URLSearchParams(window.location.search);
const uploadId = params.get("upload_id");
const progressBar = document.querySelector("#progressBar");
const stageLabel = document.querySelector("#stageLabel");
const timeLeft = document.querySelector("#timeLeft");
const skipButton = document.querySelector("#skipButton");
const errorText = document.querySelector("#errorText");
const stages = Array.from(document.querySelectorAll(".stage"));

const stageLabels = {
  queued: "대기 중",
  "pipeline starting": "파이프라인 시작 중",
  "pipeline running": "영상 처리 및 3D 재구성 중",
  "frame filtering": "영상 프레임 정리 중",
  segmentation: "발/체커보드 분리 중",
  "3D reconstruction": "3D 발 모델 생성 중",
  "mesh postprocessing": "메시 후처리 중",
  "STL export": "STL 파일 생성 중",
  "collecting artifacts": "결과 파일 정리 중",
  completed: "결과 준비 완료",
  failed: "처리 실패",
};

function stageIndexFromProgress(percent) {
  if (percent >= 85) return 3;
  if (percent >= 55) return 2;
  if (percent >= 25) return 1;
  return 0;
}

function renderJob(job) {
  const percent = Math.max(0, Math.min(100, Number(job.progress || 0)));
  const stageIndex = stageIndexFromProgress(percent);
  progressBar.style.width = `${percent}%`;
  stageLabel.textContent = stageLabels[job.stage] || job.stage || job.status;
  timeLeft.textContent = `${percent}%`;
  errorText.textContent = job.error_message || "";

  stages.forEach((stage, index) => {
    stage.classList.toggle("active", index <= stageIndex);
  });

  if (job.status === "completed") {
    skipButton.disabled = false;
    skipButton.textContent = "결과 보기";
    window.location.href = `/result?upload_id=${uploadId}`;
  } else if (job.status === "failed") {
    skipButton.disabled = false;
    skipButton.textContent = "로그 확인하기";
    timeLeft.textContent = "실패";
  } else {
    skipButton.disabled = true;
    skipButton.textContent = "결과 준비 중";
  }
}

function goResult() {
  window.location.href = `/result?upload_id=${uploadId || ""}`;
}

skipButton.addEventListener("click", goResult);

async function pollJob() {
  if (!uploadId) {
    stageLabel.textContent = "업로드 ID가 없습니다";
    timeLeft.textContent = "대기";
    errorText.textContent = "처음 화면에서 MP4 영상을 다시 업로드해 주세요.";
    return;
  }

  try {
    const response = await fetch(`/api/uploads/${uploadId}`);
    if (!response.ok) {
      throw new Error("작업 상태를 불러오지 못했습니다.");
    }

    const job = await response.json();
    renderJob(job);

    if (job.status !== "completed" && job.status !== "failed") {
      window.setTimeout(pollJob, 1500);
    }
  } catch (error) {
    stageLabel.textContent = "상태 확인 실패";
    timeLeft.textContent = "재시도 중";
    errorText.textContent = error.message;
    window.setTimeout(pollJob, 3000);
  }
}

pollJob();
