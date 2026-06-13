import * as THREE from "https://unpkg.com/three@0.169.0/build/three.module.js";
import { OrbitControls } from "https://unpkg.com/three@0.169.0/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "https://unpkg.com/three@0.169.0/examples/jsm/loaders/STLLoader.js";

const canvas = document.querySelector("#viewer");
const statusText = document.querySelector("#resultStatus");
const modelName = document.querySelector("#modelName");
const modelSelect = document.querySelector("#modelSelect");
const printButton = document.querySelector("#printButton");
const downloadLinks = {
  stl: document.querySelector("#downloadStl"),
  reportJson: document.querySelector("#downloadReportJson"),
  reportTxt: document.querySelector("#downloadReportTxt"),
};
const modelOptions = [{ name: "Prototype STL", type: "prototype", url: "" }];
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf8fafc);

const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
camera.position.set(4.5, 3, 6);

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(0, 0.2, 0);

const hemiLight = new THREE.HemisphereLight(0xffffff, 0x70665c, 2.4);
scene.add(hemiLight);

const keyLight = new THREE.DirectionalLight(0xffffff, 2.8);
keyLight.position.set(4, 6, 3);
keyLight.castShadow = true;
scene.add(keyLight);

const material = new THREE.MeshStandardMaterial({
  color: 0xf1c6a7,
  roughness: 0.7,
  metalness: 0.02,
});

const modelGroup = new THREE.Group();
scene.add(modelGroup);

function clearModel() {
  while (modelGroup.children.length > 0) {
    const child = modelGroup.children.pop();
    child.geometry?.dispose();
    child.material?.dispose();
  }
}

function addEllipsoid(name, position, scale, rotation = [0, 0, 0]) {
  const geometry = new THREE.SphereGeometry(1, 48, 32);
  const mesh = new THREE.Mesh(geometry, material.clone());
  mesh.name = name;
  mesh.position.set(...position);
  mesh.scale.set(...scale);
  mesh.rotation.set(...rotation);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  modelGroup.add(mesh);
  return mesh;
}

function showPrototypeModel() {
  clearModel();
  modelName.textContent = "Prototype STL";
  controls.target.set(0, 0.2, 0);
  camera.position.set(4.5, 3, 6);

  addEllipsoid("sole", [0, 0.32, 0], [1.1, 0.32, 2.05], [0.08, 0, 0]);
  addEllipsoid("heel", [0, 0.38, -1.52], [0.82, 0.45, 0.62]);
  addEllipsoid("arch", [0, 0.5, -0.35], [0.84, 0.38, 0.95]);
  addEllipsoid("ball", [0, 0.46, 1.28], [1.12, 0.38, 0.7]);

  const toeData = [
    [-0.58, 0.55, 1.93, 0.27, 0.23, 0.36],
    [-0.28, 0.6, 2.08, 0.3, 0.25, 0.43],
    [0.04, 0.62, 2.14, 0.32, 0.26, 0.46],
    [0.37, 0.59, 2.05, 0.28, 0.24, 0.39],
    [0.65, 0.54, 1.88, 0.23, 0.21, 0.32],
  ];

  toeData.forEach(([x, y, z, sx, sy, sz], index) => {
    addEllipsoid(`toe-${index}`, [x, y, z], [sx, sy, sz], [0.16, 0, 0]);
  });
}

function fitModelToView(mesh) {
  const box = new THREE.Box3().setFromObject(mesh);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxAxis = Math.max(size.x, size.y, size.z) || 1;
  const scale = 3.4 / maxAxis;

  mesh.position.sub(center);
  mesh.scale.setScalar(scale);

  const fittedBox = new THREE.Box3().setFromObject(mesh);
  const fittedCenter = fittedBox.getCenter(new THREE.Vector3());
  const fittedSize = fittedBox.getSize(new THREE.Vector3());
  controls.target.copy(fittedCenter);
  camera.position.set(
    fittedCenter.x + fittedSize.x * 1.4 + 2.8,
    fittedCenter.y + fittedSize.y * 1.2 + 2.2,
    fittedCenter.z + fittedSize.z * 1.5 + 3.2
  );
  camera.lookAt(fittedCenter);
  controls.update();
}

function loadStlModel(model) {
  const loader = new STLLoader();
  modelName.textContent = "로딩 중";

  loader.load(
    model.url,
    (geometry) => {
      clearModel();
      geometry.computeVertexNormals();
      const mesh = new THREE.Mesh(geometry, material.clone());
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      modelGroup.add(mesh);
      fitModelToView(mesh);
      modelName.textContent = model.name;
    },
    undefined,
    () => {
      modelName.textContent = "STL 로딩 실패";
      showPrototypeModel();
    }
  );
}

async function loadModelOptions() {
  try {
    const response = await fetch("/api/models/stl");
    if (!response.ok) return;

    const data = await response.json();
    const models = data.models || [];

    models.forEach((model) => {
      const displayName = model.name === "UMesh_final_foot_03.stl" ? "내가 준 STL" : model.name;
      addModelOption({
        name: displayName,
        type: "stl",
        url: model.url,
      });
    });
  } catch {
    showPrototypeModel();
  }
}

function addModelOption(model) {
  if (modelOptions.some((option) => option.url === model.url && option.type === model.type)) {
    return;
  }

  modelOptions.push(model);
  const option = document.createElement("option");
  option.value = model.type === "prototype" ? "prototype" : model.url;
  option.textContent = model.name;
  modelSelect.appendChild(option);
}

function selectModel(value) {
  const selected = modelOptions.find((model) => (model.type === "prototype" ? "prototype" : model.url) === value);
  if (!selected || selected.type === "prototype") {
    showPrototypeModel();
    return;
  }

  loadStlModel(selected);
}

function statusLabel(status) {
  if (status === "completed") return "완료";
  if (status === "failed") return "실패";
  if (status === "running") return "처리 중";
  if (status === "queued") return "대기 중";
  return status || "프로토타입";
}

function setDownloadLink(link, url) {
  if (!link) return;

  if (!url) {
    link.removeAttribute("href");
    link.classList.add("disabled");
    return;
  }

  link.href = url;
  link.classList.remove("disabled");
}

function applyResultDownloads(result) {
  setDownloadLink(downloadLinks.stl, result.model_stl_url);
  setDownloadLink(downloadLinks.reportJson, result.report_json_url);
  setDownloadLink(downloadLinks.reportTxt, result.report_txt_url);
}

function resize() {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  resize();
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

async function loadResultStatus() {
  const uploadId = new URLSearchParams(window.location.search).get("upload_id");
  if (!uploadId) return;

  try {
    const response = await fetch(`/api/result/${uploadId}`);
    if (!response.ok) return;
    const result = await response.json();
    statusText.textContent = statusLabel(result.status);
    applyResultDownloads(result);

    if (result.model_stl_url) {
      const uploadModel = {
        name: "Generated STL",
        type: "stl",
        url: result.model_stl_url,
      };
      addModelOption(uploadModel);
      modelSelect.value = result.model_stl_url;
      loadStlModel(uploadModel);
    }
  } catch {
    statusText.textContent = "프로토타입";
  }
}

modelSelect.addEventListener("change", () => {
  selectModel(modelSelect.value);
});

printButton.addEventListener("click", (event) => {
  event.preventDefault();
  alert("전송되었습니다!");
  window.location.href = "/";
});

showPrototypeModel();
loadResultStatus();
loadModelOptions();
animate();
