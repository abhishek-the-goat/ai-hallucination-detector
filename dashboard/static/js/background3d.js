/**
 * background3d.js
 * ---------------
 * High-aesthetic 3D cyber grid & particle space background.
 * Renders an undulating 3D wireframe terrain with floating geometric crystals
 * and depth-parallax particles. Completely non-blocking (pointer-events: none).
 */

(function () {
  'use strict';

  if (typeof THREE === 'undefined') return;

  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;

  // ── Renderer ───────────────────────────────────────────────────────
  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x07090e, 1.0);

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x07090e, 0.015);

  const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 200);
  camera.position.set(0, 12, 35);
  camera.lookAt(0, 0, 0);

  // ── Undulating 3D Cyber Wave Grid ──────────────────────────────────
  const gridW = 90;
  const gridH = 90;
  const gridSegW = 45;
  const gridSegH = 45;

  const planeGeo = new THREE.PlaneGeometry(gridW, gridH, gridSegW, gridSegH);
  planeGeo.rotateX(-Math.PI / 2);
  planeGeo.translate(0, -14, -10);

  const planeMat = new THREE.MeshBasicMaterial({
    color: 0x00f0ff,
    wireframe: true,
    transparent: true,
    opacity: 0.13,
  });
  const cyberGrid = new THREE.Mesh(planeGeo, planeMat);
  scene.add(cyberGrid);

  // Store original Y values for vertex animation
  const posAttr = planeGeo.attributes.position;
  const origY = new Float32Array(posAttr.count);
  for (let i = 0; i < posAttr.count; i++) {
    origY[i] = posAttr.getY(i);
  }

  // ── Floating 3D Cyber Polyhedra ────────────────────────────────────
  const polyGroup = new THREE.Group();
  scene.add(polyGroup);

  const geometries = [
    new THREE.IcosahedronGeometry(2.2, 0),
    new THREE.OctahedronGeometry(2.0, 0),
    new THREE.TetrahedronGeometry(2.5, 0),
    new THREE.DodecahedronGeometry(1.8, 0),
  ];

  const polyList = [];
  const POLY_COUNT = 18;

  function rand(min, max) { return min + Math.random() * (max - min); }

  for (let i = 0; i < POLY_COUNT; i++) {
    const geo = geometries[i % geometries.length];
    const isCyan = i % 2 === 0;
    const mat = new THREE.MeshBasicMaterial({
      color: isCyan ? 0x00f0ff : 0x8b5cf6,
      wireframe: true,
      transparent: true,
      opacity: rand(0.12, 0.28),
    });

    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(rand(-40, 40), rand(-5, 25), rand(-25, 10));
    mesh.scale.setScalar(rand(0.6, 1.6));

    mesh.userData = {
      rotX: rand(-0.005, 0.005),
      rotY: rand(-0.006, 0.006),
      rotZ: rand(-0.004, 0.004),
      floatSpeed: rand(0.5, 1.2),
      floatAmp: rand(0.8, 2.2),
      baseY: mesh.position.y,
      phase: Math.random() * Math.PI * 2,
    };

    polyGroup.add(mesh);
    polyList.push(mesh);
  }

  // ── Atmospheric Particle Nebula ────────────────────────────────────
  const PARTICLE_COUNT = 450;
  const pPositions = new Float32Array(PARTICLE_COUNT * 3);
  const pColors = new Float32Array(PARTICLE_COUNT * 3);

  for (let i = 0; i < PARTICLE_COUNT; i++) {
    pPositions[i * 3]     = rand(-55, 55);
    pPositions[i * 3 + 1] = rand(-15, 35);
    pPositions[i * 3 + 2] = rand(-35, 15);

    // Alternate cyan and violet particles
    if (i % 2 === 0) {
      pColors[i * 3] = 0.0;     // R
      pColors[i * 3 + 1] = 0.94; // G
      pColors[i * 3 + 2] = 1.0;  // B
    } else {
      pColors[i * 3] = 0.54;    // R
      pColors[i * 3 + 1] = 0.36; // G
      pColors[i * 3 + 2] = 0.96; // B
    }
  }

  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
  pGeo.setAttribute('color', new THREE.BufferAttribute(pColors, 3));

  const pMat = new THREE.PointsMaterial({
    size: 0.3,
    vertexColors: true,
    transparent: true,
    opacity: 0.55,
    sizeAttenuation: true,
  });
  const particleField = new THREE.Points(pGeo, pMat);
  scene.add(particleField);

  // ── Mouse Tracking with Damping ────────────────────────────────────
  let mouseX = 0;
  let mouseY = 0;
  let targetCamX = 0;
  let targetCamY = 12;

  window.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
    mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
    targetCamX = mouseX * 6;
    targetCamY = 12 - mouseY * 4;
  }, { passive: true });

  // ── Resize ─────────────────────────────────────────────────────────
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }, { passive: true });

  // ── Render Loop ────────────────────────────────────────────────────
  const clock = new THREE.Clock();

  function animate() {
    requestAnimationFrame(animate);
    const elapsed = clock.getElapsedTime();

    // Subtle camera parallax
    camera.position.x += (targetCamX - camera.position.x) * 0.02;
    camera.position.y += (targetCamY - camera.position.y) * 0.02;
    camera.lookAt(0, 0, 0);

    // Undulate the terrain wave grid
    const pos = planeGeo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const u = (i % (gridSegW + 1)) * 0.3;
      const v = Math.floor(i / (gridSegW + 1)) * 0.3;
      const wave = Math.sin(u + elapsed * 1.2) * 1.4 + Math.cos(v + elapsed * 0.9) * 1.4;
      pos.setY(i, origY[i] + wave);
    }
    pos.needsUpdate = true;

    // Rotate & float 3D polyhedra
    polyList.forEach((mesh) => {
      const d = mesh.userData;
      mesh.rotation.x += d.rotX;
      mesh.rotation.y += d.rotY;
      mesh.rotation.z += d.rotZ;
      mesh.position.y = d.baseY + Math.sin(elapsed * d.floatSpeed + d.phase) * d.floatAmp;
    });

    // Slow rotation of particles
    particleField.rotation.y = elapsed * 0.02;

    renderer.render(scene, camera);
  }

  animate();
})();
