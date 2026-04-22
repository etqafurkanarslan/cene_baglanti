import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

export class MeshViewer {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf3f4f6);
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 5000);
    this.camera.position.set(0, -180, 120);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.loader = new STLLoader();
    this.mesh = null;
    this.helmetVertices = [];
    this.assetMesh = null;
    this.baseFrame = null;
    this.currentPlacement = null;
    this.frameGroup = new THREE.Group();
    this.overlayGroup = new THREE.Group();
    this.scene.add(this.frameGroup);
    this.scene.add(this.overlayGroup);
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x555555, 1.2));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(1, -1, 2);
    this.scene.add(dir);

    window.addEventListener("resize", () => this.resize());
    this.resize();
    this.animate();
  }

  async loadCase(caseDetail, placement) {
    this.clear();
    const helmetGeometry = await this.loader.loadAsync(caseDetail.artifact_urls.mesh);
    helmetGeometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({ color: 0xb5bcc8, metalness: 0.0, roughness: 0.92 });
    this.mesh = new THREE.Mesh(helmetGeometry, material);
    this.mesh.name = "helmet";
    this.scene.add(this.mesh);
    this.helmetVertices = extractVertices(helmetGeometry);

    const assetGeometry = await this.loader.loadAsync(caseDetail.artifact_urls.mount_asset_mesh);
    assetGeometry.computeVertexNormals();
    this.assetMesh = new THREE.Mesh(
      assetGeometry,
      new THREE.MeshStandardMaterial({ color: 0x7c3aed, transparent: true, opacity: 0.45 }),
    );
    this.assetMesh.name = "ghostMount";
    this.assetMesh.userData.persistent = true;
    this.overlayGroup.add(this.assetMesh);

    this.fitCamera(helmetGeometry);
    this.baseFrame = cloneFrame(caseDetail.result.mount_frame);
    this.currentPlacement = normalizePlacement(caseDetail.result, placement);
    this.drawFrame(caseDetail.result.mount_frame);
    this.drawMarker(caseDetail.result.mount_frame.origin, 0xff7a00, 2.4, "autoCenter", true);
    if (caseDetail.result.placement?.legacy_center) {
      this.drawMarker(caseDetail.result.placement.legacy_center, 0xdd3333, 1.8, "legacyCenter", true);
    }
    this.updatePlacementPreview(this.currentPlacement, caseDetail.result);
  }

  setWireframe(enabled) {
    if (this.mesh) {
      this.mesh.material.wireframe = enabled;
    }
  }

  updatePlacementPreview(placement, result) {
    if (!this.assetMesh || !this.baseFrame) {
      return;
    }
    this.currentPlacement = { ...placement };
    this.clearDynamicOverlays();

    const frame = buildFrameFromPlacement(this.baseFrame, placement);
    this.currentPlacement.frame = frame;
    this.applyAssetTransform(frame);
    this.drawMarker(placement.mount_center, 0x111111, 2.0, "placementCenter", true);
    this.drawFrame(frame, "placementFrame");

    const width = result.saddle.footprint_width_mm;
    const height = result.saddle.footprint_height_mm;
    const topLoop = sampleEllipse(frame, width, height, result.saddle.saddle_height_mm);
    const projectedLoop = projectFootprintOntoHelmet(frame, width, height, placement.footprint_margin_mm, this.helmetVertices);
    this.drawLoop(topLoop, 0x111111, "footprintTop");
    this.drawLoop(projectedLoop, 0x059669, "footprintProjected");
  }

  pick(event) {
    if (!this.mesh) {
      return null;
    }
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hits = this.raycaster.intersectObject(this.mesh, false);
    if (!hits.length) {
      return null;
    }
    const hit = hits[0];
    return {
      faceId: hit.faceIndex,
      point: [hit.point.x, hit.point.y, hit.point.z],
    };
  }

  setSelection(selectionState) {
    this.clearSelectionMarkers();
    if (!this.mesh) {
      return;
    }
    const position = this.mesh.geometry.attributes.position.array;
    for (const faceId of selectionState.includedFaceIds) {
      this.drawFaceCentroid(position, faceId, 0x33aa33);
    }
    for (const faceId of selectionState.excludedFaceIds) {
      this.drawFaceCentroid(position, faceId, 0xcc3333);
    }
  }

  clear() {
    if (this.mesh) {
      this.scene.remove(this.mesh);
      this.mesh.geometry.dispose();
      this.mesh.material.dispose();
      this.mesh = null;
    }
    this.helmetVertices = [];
    this.assetMesh = null;
    this.baseFrame = null;
    this.currentPlacement = null;
    this.frameGroup.clear();
    this.overlayGroup.clear();
  }

  clearSelectionMarkers() {
    const keep = this.overlayGroup.children.filter((child) => child.userData?.persistent);
    this.overlayGroup.clear();
    keep.forEach((child) => this.overlayGroup.add(child));
  }

  clearDynamicOverlays() {
    const keep = this.overlayGroup.children.filter((child) => child.userData?.persistent);
    this.overlayGroup.clear();
    keep.forEach((child) => this.overlayGroup.add(child));
  }

  drawFrame(frame, key = "frame") {
    const origin = new THREE.Vector3(...frame.origin);
    const axes = [
      { vector: frame.x_axis, color: 0xdc2626 },
      { vector: frame.y_axis, color: 0x16a34a },
      { vector: frame.z_axis, color: 0x2563eb },
    ];
    for (const axis of axes) {
      const end = origin.clone().add(new THREE.Vector3(...axis.vector).multiplyScalar(20));
      const geometry = new THREE.BufferGeometry().setFromPoints([origin, end]);
      const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: axis.color }));
      line.userData = { key, persistent: true };
      this.overlayGroup.add(line);
    }
  }

  drawLoop(points, color, key) {
    const geometry = new THREE.BufferGeometry().setFromPoints(points.map((point) => new THREE.Vector3(...point)));
    const loop = new THREE.LineLoop(geometry, new THREE.LineBasicMaterial({ color }));
    loop.userData = { key, persistent: true };
    this.overlayGroup.add(loop);
  }

  drawMarker(point, color, radius = 1.5, key = "", persistent = true) {
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 16, 16),
      new THREE.MeshStandardMaterial({ color }),
    );
    sphere.position.set(...point);
    sphere.userData = { key, persistent };
    if (key) {
      const existing = this.overlayGroup.children.find((child) => child.userData?.key === key);
      if (existing) {
        this.overlayGroup.remove(existing);
      }
    }
    this.overlayGroup.add(sphere);
  }

  drawFaceCentroid(positionArray, faceId, color) {
    const baseIndex = faceId * 9;
    if (baseIndex + 8 >= positionArray.length) {
      return;
    }
    const centroid = [
      (positionArray[baseIndex] + positionArray[baseIndex + 3] + positionArray[baseIndex + 6]) / 3,
      (positionArray[baseIndex + 1] + positionArray[baseIndex + 4] + positionArray[baseIndex + 7]) / 3,
      (positionArray[baseIndex + 2] + positionArray[baseIndex + 5] + positionArray[baseIndex + 8]) / 3,
    ];
    this.drawMarker(centroid, color, 1.1, "", false);
  }

  applyAssetTransform(frame) {
    if (!this.assetMesh) {
      return;
    }
    const basis = new THREE.Matrix4().makeBasis(
      new THREE.Vector3(...frame.x_axis),
      new THREE.Vector3(...frame.y_axis),
      new THREE.Vector3(...frame.z_axis),
    );
    basis.setPosition(new THREE.Vector3(...frame.origin));
    this.assetMesh.matrixAutoUpdate = false;
    this.assetMesh.matrix.copy(basis);
  }

  fitCamera(geometry) {
    geometry.computeBoundingBox();
    const box = geometry.boundingBox;
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);
    this.controls.target.copy(center);
    const radius = Math.max(size.x, size.y, size.z) * 1.2;
    this.camera.position.set(center.x, center.y - radius * 1.5, center.z + radius);
    this.camera.near = Math.max(0.1, radius / 100);
    this.camera.far = radius * 10;
    this.camera.updateProjectionMatrix();
  }

  resize() {
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
}

function cloneFrame(frame) {
  return {
    origin: [...frame.origin],
    x_axis: [...frame.x_axis],
    y_axis: [...frame.y_axis],
    z_axis: [...frame.z_axis],
  };
}

function normalizePlacement(result, placement) {
  if (placement) {
    return {
      mount_center: [...placement.mount_center],
      mount_rotation_euler_deg: [...placement.mount_rotation_euler_deg],
      mount_offset_mm: placement.mount_offset_mm ?? 0,
      footprint_margin_mm: placement.footprint_margin_mm ?? 2,
    };
  }
  return {
    mount_center: [...result.mount_frame.origin],
    mount_rotation_euler_deg: [0, 0, 0],
    mount_offset_mm: 0,
    footprint_margin_mm: 2,
  };
}

function buildFrameFromPlacement(baseFrame, placement) {
  const rotation = new THREE.Euler(
    THREE.MathUtils.degToRad(placement.mount_rotation_euler_deg[0] || 0),
    THREE.MathUtils.degToRad(placement.mount_rotation_euler_deg[1] || 0),
    THREE.MathUtils.degToRad(placement.mount_rotation_euler_deg[2] || 0),
    "XYZ",
  );
  const basis = new THREE.Matrix4().makeBasis(
    new THREE.Vector3(...baseFrame.x_axis),
    new THREE.Vector3(...baseFrame.y_axis),
    new THREE.Vector3(...baseFrame.z_axis),
  );
  const localRotation = new THREE.Matrix4().makeRotationFromEuler(rotation);
  const rotatedBasis = new THREE.Matrix4().multiplyMatrices(basis, localRotation);
  const xAxis = new THREE.Vector3(1, 0, 0).applyMatrix4(rotatedBasis).normalize();
  const yAxis = new THREE.Vector3(0, 1, 0).applyMatrix4(rotatedBasis).normalize();
  const zAxis = new THREE.Vector3(0, 0, 1).applyMatrix4(rotatedBasis).normalize();
  const contactCenter = new THREE.Vector3(...placement.mount_center);
  const origin = contactCenter.clone().addScaledVector(zAxis, placement.mount_offset_mm || 0);
  return {
    origin: [origin.x, origin.y, origin.z],
    x_axis: [xAxis.x, xAxis.y, xAxis.z],
    y_axis: [yAxis.x, yAxis.y, yAxis.z],
    z_axis: [zAxis.x, zAxis.y, zAxis.z],
  };
}

function sampleEllipse(frame, width, height, zOffset) {
  const origin = new THREE.Vector3(...frame.origin);
  const xAxis = new THREE.Vector3(...frame.x_axis);
  const yAxis = new THREE.Vector3(...frame.y_axis);
  const zAxis = new THREE.Vector3(...frame.z_axis);
  const halfWidth = width * 0.5;
  const halfHeight = height * 0.5;
  const points = [];
  for (let i = 0; i < 64; i += 1) {
    const angle = (Math.PI * 2 * i) / 64;
    const point = origin.clone()
      .addScaledVector(xAxis, Math.cos(angle) * halfWidth)
      .addScaledVector(yAxis, Math.sin(angle) * halfHeight)
      .addScaledVector(zAxis, zOffset || 0);
    points.push([point.x, point.y, point.z]);
  }
  return points;
}

function projectFootprintOntoHelmet(frame, width, height, margin, helmetVertices) {
  if (!helmetVertices.length) {
    return sampleEllipse(frame, width, height, 0);
  }
  const origin = new THREE.Vector3(...frame.origin);
  const xAxis = new THREE.Vector3(...frame.x_axis);
  const yAxis = new THREE.Vector3(...frame.y_axis);
  const zAxis = new THREE.Vector3(...frame.z_axis);
  const halfWidth = width * 0.5 + margin;
  const halfHeight = height * 0.5 + margin;
  const points = [];
  for (let i = 0; i < 64; i += 1) {
    const angle = (Math.PI * 2 * i) / 64;
    const sample = {
      x: Math.cos(angle) * halfWidth,
      y: Math.sin(angle) * halfHeight,
    };
    let best = null;
    let bestScore = Number.POSITIVE_INFINITY;
    for (const vertex of helmetVertices) {
      const vector = new THREE.Vector3(...vertex).sub(origin);
      const localX = vector.dot(xAxis);
      const localY = vector.dot(yAxis);
      const localZ = vector.dot(zAxis);
      const xyScore = Math.hypot(localX - sample.x, localY - sample.y);
      if (localZ > 5) {
        continue;
      }
      const score = xyScore + Math.abs(localZ) * 0.1;
      if (score < bestScore) {
        bestScore = score;
        best = vertex;
      }
    }
    points.push(best || [
      origin.x + sample.x * xAxis.x + sample.y * yAxis.x,
      origin.y + sample.x * xAxis.y + sample.y * yAxis.y,
      origin.z + sample.x * xAxis.z + sample.y * yAxis.z,
    ]);
  }
  return points;
}

function extractVertices(geometry) {
  const positions = geometry.attributes.position.array;
  const vertices = [];
  for (let index = 0; index < positions.length; index += 3) {
    vertices.push([positions[index], positions[index + 1], positions[index + 2]]);
  }
  return vertices;
}

