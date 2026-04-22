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

  async loadCase(caseDetail) {
    this.clear();
    const geometry = await this.loader.loadAsync(caseDetail.artifact_urls.mesh);
    geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({ color: 0xb5bcc8, metalness: 0.0, roughness: 0.9 });
    this.mesh = new THREE.Mesh(geometry, material);
    this.mesh.name = "helmet";
    this.scene.add(this.mesh);
    this.fitCamera(geometry);
    this.drawFrame(caseDetail.result.mount_frame);
    this.drawMountCenter(caseDetail.result.mount_frame.origin, 0xff7a00);
    if (caseDetail.result.placement?.legacy_center) {
      this.drawMarker(caseDetail.result.placement.legacy_center, 0xdd3333, 1.9);
    }
    if (caseDetail.result.placement?.anchor_point) {
      this.drawMarker(caseDetail.result.placement.anchor_point, 0xcc00ff, 1.7);
    }
    this.drawFootprint(caseDetail.result);
  }

  setWireframe(enabled) {
    if (this.mesh) {
      this.mesh.material.wireframe = enabled;
    }
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
    if (selectionState.manualCenter) {
      this.drawMountCenter(selectionState.manualCenter, 0x111111, "manualCenter");
    }
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

  clear() {
    if (this.mesh) {
      this.scene.remove(this.mesh);
      this.mesh.geometry.dispose();
      this.mesh.material.dispose();
      this.mesh = null;
    }
    this.frameGroup.clear();
    this.overlayGroup.clear();
  }

  clearSelectionMarkers() {
    const keep = this.overlayGroup.children.filter((child) => child.userData?.persistent);
    this.overlayGroup.clear();
    keep.forEach((child) => this.overlayGroup.add(child));
  }

  drawFrame(frame) {
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
      this.frameGroup.add(line);
    }
  }

  drawFootprint(result) {
    const frame = result.mount_frame;
    const width = result.saddle.footprint_width_mm * 0.5;
    const height = result.saddle.footprint_height_mm * 0.5;
    const origin = new THREE.Vector3(...frame.origin);
    const xAxis = new THREE.Vector3(...frame.x_axis);
    const yAxis = new THREE.Vector3(...frame.y_axis);
    const points = [];
    for (let i = 0; i < 64; i += 1) {
      const angle = (Math.PI * 2 * i) / 64;
      const point = origin.clone()
        .addScaledVector(xAxis, Math.cos(angle) * width)
        .addScaledVector(yAxis, Math.sin(angle) * height);
      points.push(point);
    }
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const loop = new THREE.LineLoop(geometry, new THREE.LineBasicMaterial({ color: 0x111111 }));
    loop.userData.persistent = true;
    this.overlayGroup.add(loop);
  }

  drawMountCenter(point, color, key = "mountCenter") {
    this.drawMarker(point, color, 2.4, key, true);
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

