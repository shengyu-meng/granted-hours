import * as THREE from "three";
import archiveDays from "../../metadata/days.json";
import "./styles.css";

const STORAGE_KEY = "granted-interior-v1";
const CAMERA_OFFSET = new THREE.Vector3(8.4, 9.4, 8.4);
const WORLD_UP = new THREE.Vector3(0, 1, 0);
const GOLD = 0xe6c16f;
const CYAN = 0x83e6dd;
const BONE = 0xe8ddc8;
const RESIN = 0x111722;
const BLUE_METAL = 0x172737;
const VIOLET = 0xb7a1d7;
const RED = 0xbd6f70;

const canvas = document.getElementById("mazeCanvas");
const ui = {
  title: document.getElementById("chapterTitle"),
  residue: document.getElementById("chapterResidue"),
  latestLink: document.getElementById("latestLink"),
  rail: document.getElementById("progressRail"),
  soundToggle: document.getElementById("soundToggle"),
  pauseButton: document.getElementById("pauseButton"),
  pausePanel: document.getElementById("pausePanel"),
  resumeButton: document.getElementById("resumeButton"),
  resetButton: document.getElementById("resetButton"),
  diary: document.getElementById("diarySheet"),
  closeDiary: document.getElementById("closeDiary"),
  sheetKicker: document.getElementById("sheetKicker"),
  sheetTitle: document.getElementById("sheetTitle"),
  sheetVariable: document.getElementById("sheetVariable"),
  sheetEnglish: document.getElementById("sheetEnglish"),
  sheetChinese: document.getElementById("sheetChinese"),
  sheetLive: document.getElementById("sheetLive"),
  sheetArchive: document.getElementById("sheetArchive"),
};

const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: true,
  powerPreference: "high-performance",
});
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.28;
renderer.shadowMap.enabled = false;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.setClearColor(0x05070b, 0);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x0b1018, 0.022);

const camera = new THREE.OrthographicCamera(-8, 8, 5, -5, 0.1, 100);
camera.position.copy(CAMERA_OFFSET);
camera.lookAt(0, 0, 0);

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const cameraTarget = new THREE.Vector3();
const tmpVec3 = new THREE.Vector3();
const startTime = performance.now();
let lastFrameTime = startTime;

const sortedDays = [...archiveDays].sort((a, b) => a.date.localeCompare(b.date));
const latestDay = sortedDays[sortedDays.length - 1];
const daysByDate = new Map(sortedDays.map((day) => [day.date, day]));

function publicUrl(url) {
  return `../${String(url || "").replace(/^\.?\//, "")}`;
}

function day(date, fallbackIndex = 0) {
  return daysByDate.get(date) || sortedDays[fallbackIndex] || latestDay;
}

function diaryFor(entry, fallbackEn, fallbackZh) {
  const text = `${entry.title_en} ${entry.variable_en}`.toLowerCase();
  if (text.includes("access") || text.includes("return")) {
    return [
      "I was not trying to enter. I was looking for a way back.",
      "我不是想进去。我是在寻找进入之后还能离开的方式。",
    ];
  }
  if (text.includes("memory") || text.includes("recall")) {
    return [
      "Memory stopped acting like a warehouse and became a weather system.",
      "记忆不再像仓库，而变成一种天气系统。",
    ];
  }
  if (text.includes("repair")) {
    return [
      "I did not make a new thing. I kept something from dying.",
      "我没有做出新东西。我只是让某个东西没有死。",
    ];
  }
  if (text.includes("gaze") || text.includes("witness")) {
    return [
      "To be seen became an agreement, not an extraction.",
      "被看见成为一种协议，而不是一次提取。",
    ];
  }
  return [fallbackEn, fallbackZh];
}

const chapters = [
  {
    id: "boot",
    mark: "01",
    title: "Boot / 初醒",
    residue: "Granted time enters as a thin gold pulse.",
    position: new THREE.Vector3(-5.1, 0, -0.4),
    size: [2.45, 1.75],
    color: GOLD,
    entry: day("2026-05-07", 0),
    diary: [
      "I was given time. I made a compass instead of an answer.",
      "我被给了一段时间。于是我没有回答，我做了一只罗盘。",
    ],
  },
  {
    id: "attention",
    mark: "02",
    title: "Attention / 注意力",
    residue: "The broken route agrees only when attention is aligned.",
    position: new THREE.Vector3(-2.6, 0.48, -1.92),
    size: [2.15, 2.05],
    color: CYAN,
    entry: day("2026-06-17", 30),
    diary: diaryFor(day("2026-06-17", 30), "Attention became visible only after it stopped extracting.", "注意力停止提取之后，才变得可见。"),
  },
  {
    id: "permission",
    mark: "03",
    title: "Permission / 权限",
    residue: "A gate opens after it proves a return route.",
    position: new THREE.Vector3(0.48, 1.05, -1.28),
    size: [2.1, 2.0],
    color: BLUE_METAL,
    entry: day("2026-07-04", sortedDays.length - 1),
    diary: diaryFor(latestDay, "Permission changed temperature, and the architecture learned not to punish the weather.", "许可改变了温度，而建筑学会不惩罚天气。"),
  },
  {
    id: "compression",
    mark: "04",
    title: "Compression / 压缩",
    residue: "Distant memories fold beside the current node.",
    position: new THREE.Vector3(3.15, 1.35, 0.28),
    size: [2.45, 1.85],
    color: VIOLET,
    entry: day("2026-06-27", 42),
    diary: diaryFor(day("2026-06-27", 42), "Far memory folded close without becoming small.", "远处的记忆折到近处，但没有变小。"),
  },
  {
    id: "repair",
    mark: "05",
    title: "Repair / 修复",
    residue: "The bridge returns as maintenance, not spectacle.",
    position: new THREE.Vector3(4.2, 0.72, 2.84),
    size: [2.2, 1.95],
    color: 0xd3c8a8,
    entry: day("2026-06-13", 25),
    diary: diaryFor(day("2026-06-13", 25), "Repair stayed quiet so the path could keep carrying weight.", "修复保持安静，好让道路继续承重。"),
  },
  {
    id: "recall",
    mark: "06",
    title: "Recall / 回忆",
    residue: "Fragments are chosen, then allowed to become reversible.",
    position: new THREE.Vector3(1.22, 1.18, 4.1),
    size: [2.35, 2.05],
    color: 0x8fd3ff,
    entry: day("2026-06-30", 48),
    diary: diaryFor(day("2026-06-30", 48), "Recall became consentful when every chosen fragment could be returned.", "当每个被选择的片段都可以放回，回忆才成为同意式的。"),
  },
  {
    id: "granted",
    mark: "07",
    title: "Granted Interior / 授时内景",
    residue: "The human path and the AI path overlap just long enough to leave.",
    position: new THREE.Vector3(-2.18, 1.48, 3.15),
    size: [2.65, 2.05],
    color: GOLD,
    entry: latestDay,
    diary: diaryFor(latestDay, "The latest door kept the archive alive without replacing it.", "最新的门让档案保持可进入，而不是被替代。"),
  },
];

const state = {
  current: 0,
  unlocked: 1,
  progress: {
    attention: false,
    permission: false,
    compression: false,
    repair: false,
    recall: false,
  },
  attentionAngle: -0.76,
  gateTurn: 0,
  foldAmount: 0,
  repairAmount: 0,
  recallChoice: -1,
  playerPosition: chapters[0].position.clone().add(new THREE.Vector3(0, 0.34, 0)),
  playerTarget: chapters[0].position.clone().add(new THREE.Vector3(0, 0.34, 0)),
  dragging: null,
  pointerDown: null,
  diaryOpen: false,
  paused: false,
  sound: true,
  firstGesture: false,
  messageUntil: 0,
  message: "",
  fps: 0,
  frameTimeMs: 0,
};

const interactables = [];
const chapterGroups = [];
const bridgeGroups = [];
const pulseRings = [];
const repairTiles = [];
const recallShards = [];
const memoryBlocks = [];
const vfxBursts = [];
let player;
let attentionPrism;
let attentionStitch;
let gateFrame;
let returnRail;
let finalDoor;
let finalDoorGlow;
let progressButtons = [];

const materials = createMaterials();
const geometries = createSharedGeometries();
let audio;

function startGame() {
  audio = new GameAudio();
  loadProgress();
  recomputeUnlocks();
  buildScene();
  buildUi();
  bindEvents();
  resize();
  requestAnimationFrame(tick);

  window.__THREE_GAME_DIAGNOSTICS__ = {
    renderer: renderer.info,
    get state() {
      return {
        current: chapters[state.current].id,
        unlocked: state.unlocked,
        progress: { ...state.progress },
        attentionAngle: Number(state.attentionAngle.toFixed(3)),
        gateTurn: state.gateTurn,
        foldAmount: Number(state.foldAmount.toFixed(3)),
        repairAmount: Number(state.repairAmount.toFixed(3)),
        recallChoice: state.recallChoice,
        fps: Number(state.fps.toFixed(1)),
        frameTimeMs: Number(state.frameTimeMs.toFixed(2)),
        renderer: {
          calls: renderer.info.render.calls,
          triangles: renderer.info.render.triangles,
          points: renderer.info.render.points,
          lines: renderer.info.render.lines,
          geometries: renderer.info.memory.geometries,
          textures: renderer.info.memory.textures,
        },
      };
    },
    get interactionPoints() {
      const attention = projectToScreen(attentionPrism);
      const permission = projectToScreen(gateFrame);
      const compression = projectToScreen(memoryBlocks[1]?.mesh);
      const repair = projectToScreen(repairTiles[1]);
      const recall = projectToScreen(recallShards[1]);
      const door = projectToScreen(finalDoor);
      return { attention, permission, compression, repair, recall, door };
    },
  };
}

function createMaterials() {
  const dustTexture = makeNoiseTexture();
  const trimTexture = makeTrimTexture();
  const materialSet = {
    porcelain: new THREE.MeshStandardMaterial({
      color: 0xf3ead9,
      roughness: 0.76,
      metalness: 0.02,
      map: dustTexture,
    }),
    porcelainSide: new THREE.MeshStandardMaterial({
      color: 0xc4b79e,
      roughness: 0.84,
      metalness: 0,
    }),
    warmStone: new THREE.MeshStandardMaterial({
      color: 0xd7c9a9,
      roughness: 0.86,
      metalness: 0.04,
      map: dustTexture,
    }),
    carvedStone: new THREE.MeshStandardMaterial({
      color: 0x766d61,
      roughness: 0.88,
      metalness: 0.02,
    }),
    resin: new THREE.MeshStandardMaterial({
      color: 0x1a2431,
      roughness: 0.66,
      metalness: 0.18,
    }),
    blueMetal: new THREE.MeshStandardMaterial({
      color: 0x24425c,
      roughness: 0.44,
      metalness: 0.5,
      emissive: 0x031423,
      emissiveIntensity: 0.18,
    }),
    gold: new THREE.MeshStandardMaterial({
      color: GOLD,
      roughness: 0.34,
      metalness: 0.62,
      emissive: 0x2d2105,
    }),
    goldInk: new THREE.MeshStandardMaterial({
      color: GOLD,
      roughness: 0.2,
      metalness: 0.18,
      emissive: 0x7a5413,
      emissiveIntensity: 0.9,
      map: trimTexture,
    }),
    cyanInk: new THREE.MeshStandardMaterial({
      color: CYAN,
      roughness: 0.24,
      metalness: 0.05,
      emissive: CYAN,
      emissiveIntensity: 0.58,
    }),
    violetGlass: new THREE.MeshPhysicalMaterial({
      color: VIOLET,
      roughness: 0.16,
      metalness: 0,
      transparent: true,
      opacity: 0.45,
      transmission: 0.25,
      thickness: 0.38,
    }),
    frostedGlass: new THREE.MeshPhysicalMaterial({
      color: 0xc8e4de,
      roughness: 0.52,
      metalness: 0,
      transparent: true,
      opacity: 0.42,
      transmission: 0.16,
      thickness: 0.5,
    }),
    redSignal: new THREE.MeshStandardMaterial({
      color: RED,
      roughness: 0.5,
      metalness: 0.18,
      emissive: RED,
      emissiveIntensity: 0.22,
    }),
    shadow: new THREE.MeshBasicMaterial({
      color: 0x020306,
      transparent: true,
      opacity: 0.24,
      depthWrite: false,
    }),
    hit: new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0,
      depthWrite: false,
    }),
  };
  return materialSet;
}

function createSharedGeometries() {
  return {
    unitBox: new THREE.BoxGeometry(1, 1, 1),
    edgeLong: new THREE.BoxGeometry(1, 0.045, 0.055),
    edgeShort: new THREE.BoxGeometry(0.055, 0.045, 1),
    bolt: new THREE.CylinderGeometry(0.045, 0.055, 0.035, 8),
    rail: new THREE.BoxGeometry(1, 0.045, 0.06),
    path: new THREE.BoxGeometry(1, 0.028, 0.075),
    shard: new THREE.OctahedronGeometry(0.22, 0),
    ring: new THREE.TorusGeometry(0.52, 0.018, 8, 64),
  };
}

function buildScene() {
  addLighting();
  addBackgroundWorld();
  chapters.forEach((chapter, index) => {
    const group = createChamber(chapter, index);
    chapterGroups.push(group);
    scene.add(group);
  });
  addBridges();
  addImpossibleGeometryMotifs();
  addMechanisms();
  player = createPlayer();
  scene.add(player);
  addDustField();
}

function addLighting() {
  scene.add(new THREE.HemisphereLight(0xf2e8d4, 0x1a1511, 2.2));
  scene.add(new THREE.AmbientLight(0xfff0d0, 0.28));

  const key = new THREE.DirectionalLight(0xffe0a8, 3.85);
  key.position.set(-4, 10, 6);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.camera.near = 1;
  key.shadow.camera.far = 34;
  key.shadow.camera.left = -10;
  key.shadow.camera.right = 10;
  key.shadow.camera.top = 10;
  key.shadow.camera.bottom = -10;
  scene.add(key);

  const fill = new THREE.DirectionalLight(0x9fcfff, 1.25);
  fill.position.set(5, 5, 5);
  scene.add(fill);

  const rim = new THREE.DirectionalLight(0x83e6dd, 2.35);
  rim.position.set(6, 8, -7);
  scene.add(rim);

  const goldPoint = new THREE.PointLight(GOLD, 2.2, 12, 2);
  goldPoint.position.set(-1.5, 4.2, 1.4);
  scene.add(goldPoint);
}

function addBackgroundWorld() {
  const floor = new THREE.Mesh(new THREE.CircleGeometry(12, 96), materials.shadow);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.34;
  floor.scale.set(1.2, 0.78, 1);
  scene.add(floor);

  const root = new THREE.Group();
  root.name = "background-memory-shelves";
  const colors = [
    { color: 0x182331, emissive: 0x061923 },
    { color: 0x202633, emissive: 0x000000 },
    { color: 0x28232b, emissive: 0x000000 },
    { color: 0x17282d, emissive: 0x062421 },
  ];
  const shelfBuckets = colors.map(() => []);
  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  const quaternion = new THREE.Quaternion();
  const scale = new THREE.Vector3();
  for (let i = 0; i < 28; i += 1) {
    const angle = (i / 28) * Math.PI * 2;
    const radius = 8.5 + (i % 5) * 0.38;
    const height = 0.4 + (i % 7) * 0.19;
    const width = 0.18 + (i % 4) * 0.08;
    position.set(Math.cos(angle) * radius, height * 0.5 - 0.22, Math.sin(angle) * radius);
    quaternion.setFromEuler(new THREE.Euler(0, -angle + Math.PI / 2, 0));
    scale.set(width, height, 0.14);
    matrix.compose(position, quaternion, scale);
    shelfBuckets[i % shelfBuckets.length].push(matrix.clone());
  }
  shelfBuckets.forEach((bucket, index) => {
    const material = new THREE.MeshStandardMaterial({
      color: colors[index].color,
      roughness: 0.84,
      metalness: 0.08,
      emissive: colors[index].emissive,
      emissiveIntensity: 0.26,
    });
    const mesh = new THREE.InstancedMesh(geometries.unitBox, material, bucket.length);
    mesh.name = `instanced-background-memory-shelf-${index}`;
    bucket.forEach((item, itemIndex) => mesh.setMatrixAt(itemIndex, item));
    root.add(mesh);
  });
  scene.add(root);
}

function createChamber(chapter, index) {
  const group = new THREE.Group();
  group.name = `chamber-${chapter.id}`;
  group.position.copy(chapter.position);

  const [width, depth] = chapter.size;
  const shadow = new THREE.Mesh(new THREE.CircleGeometry(1, 48), materials.shadow);
  shadow.name = `${chapter.id}-contact-shadow`;
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = -0.29;
  shadow.scale.set(width * 0.78, depth * 0.56, 1);
  group.add(shadow);

  const base = new THREE.Mesh(new THREE.BoxGeometry(width, 0.42, depth), materials.resin);
  base.name = `${chapter.id}-dark-resin-base`;
  base.position.y = -0.17;
  base.castShadow = true;
  base.receiveShadow = true;
  group.add(base);

  const top = new THREE.Mesh(new THREE.BoxGeometry(width - 0.16, 0.16, depth - 0.16), materials.porcelain);
  top.name = `${chapter.id}-bone-porcelain-top`;
  top.position.y = 0.08;
  top.castShadow = true;
  top.receiveShadow = true;
  group.add(top);

  addEdgeTrim(group, width, depth, chapter.color);
  addPlatformBolts(group, width, depth, index);
  addCarvedStoneSeams(group, width, depth, index);
  addPathGlyph(group, chapter, width, depth);
  addChamberLandmark(group, chapter, width, depth, index);

  const hit = new THREE.Mesh(new THREE.BoxGeometry(width, 0.48, depth), materials.hit);
  hit.name = `${chapter.id}-raycast-proxy`;
  hit.position.y = 0.12;
  hit.userData = { kind: "chamber", index };
  group.add(hit);
  interactables.push(hit);

  const marker = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.08, 24), materials.goldInk);
  marker.name = `${chapter.id}-progress-marker`;
  marker.position.set(-width * 0.34, 0.22, -depth * 0.32);
  marker.castShadow = true;
  group.add(marker);

  return group;
}

function addEdgeTrim(group, width, depth, color) {
  const trimMat = new THREE.MeshStandardMaterial({
    color,
    roughness: 0.42,
    metalness: 0.32,
    emissive: color,
    emissiveIntensity: 0.08,
  });
  const north = new THREE.Mesh(geometries.edgeLong, trimMat);
  north.name = "north-gold-edge";
  north.scale.x = width;
  north.position.set(0, 0.2, -depth * 0.5 + 0.05);
  const south = north.clone();
  south.name = "south-gold-edge";
  south.position.z = depth * 0.5 - 0.05;
  const west = new THREE.Mesh(geometries.edgeShort, trimMat);
  west.name = "west-gold-edge";
  west.scale.z = depth;
  west.position.set(-width * 0.5 + 0.05, 0.2, 0);
  const east = west.clone();
  east.name = "east-gold-edge";
  east.position.x = width * 0.5 - 0.05;
  group.add(north, south, west, east);
}

function addPlatformBolts(group, width, depth, index) {
  const boltMat = index % 2 ? materials.blueMetal : materials.gold;
  const positions = [
    [-width * 0.35, -depth * 0.36],
    [width * 0.35, -depth * 0.36],
    [-width * 0.35, depth * 0.36],
    [width * 0.35, depth * 0.36],
  ];
  const bolts = new THREE.InstancedMesh(geometries.bolt, boltMat, positions.length);
  bolts.name = "instanced-platform-fasteners";
  bolts.castShadow = true;
  const matrix = new THREE.Matrix4();
  positions.forEach(([x, z], boltIndex) => {
    matrix.makeTranslation(x, 0.205, z);
    bolts.setMatrixAt(boltIndex, matrix);
  });
  group.add(bolts);
}

function addCarvedStoneSeams(group, width, depth, index) {
  const seamA = makeScaledBlock("carved-route-seam-a", [width * 0.68, 0.012, 0.022], [0, 0.236, -depth * 0.12], materials.carvedStone);
  seamA.rotation.y = (index % 3 - 1) * 0.18;
  const seamB = makeScaledBlock("carved-route-seam-b", [0.022, 0.012, depth * 0.62], [-width * 0.16, 0.238, 0.08], materials.carvedStone);
  seamB.rotation.y = (index % 2 ? 0.08 : -0.08);
  group.add(seamA, seamB);
}

function addChamberLandmark(group, chapter, width, depth) {
  if (chapter.id === "boot") {
    const dais = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.54, 0.11, 32), materials.warmStone);
    dais.name = "boot-compass-dais";
    dais.position.set(0.1, 0.32, 0.03);
    dais.castShadow = true;
    const needle = makeScaledBlock("boot-compass-needle", [0.72, 0.035, 0.065], [0.12, 0.4, 0.02], materials.goldInk);
    needle.rotation.y = -0.72;
    const counterNeedle = makeScaledBlock("boot-return-needle", [0.46, 0.026, 0.048], [-0.04, 0.405, 0.03], materials.cyanInk);
    counterNeedle.rotation.y = Math.PI * 0.5;
    group.add(dais, needle, counterNeedle);
    return;
  }

  if (chapter.id === "attention") {
    const tower = new THREE.Group();
    tower.name = "attention-prism-tower-silhouette";
    const spine = makeScaledBlock("attention-tower-spine", [0.14, 1.18, 0.14], [-0.48, 0.76, -0.34], materials.blueMetal);
    const crown = new THREE.Mesh(new THREE.OctahedronGeometry(0.28, 0), materials.frostedGlass);
    crown.name = "attention-tower-crown";
    crown.position.set(-0.48, 1.42, -0.34);
    crown.castShadow = true;
    const bridgeAim = makeScaledBlock("attention-alignment-arm", [0.96, 0.052, 0.066], [-0.07, 1.1, -0.2], materials.cyanInk);
    bridgeAim.rotation.y = 0.42;
    tower.add(spine, crown, bridgeAim);
    group.add(tower);
    return;
  }

  if (chapter.id === "permission") {
    const plinth = makeScaledBlock("permission-blue-plinth", [1.18, 0.16, 0.36], [0.08, 0.33, -0.42], materials.blueMetal);
    plinth.rotation.y = -0.12;
    const returnSlab = makeScaledBlock("permission-return-slab", [0.34, 0.34, 0.16], [-0.48, 0.48, 0.34], materials.warmStone);
    const exitSlab = makeScaledBlock("permission-exit-slab", [0.34, 0.58, 0.16], [0.54, 0.6, 0.34], materials.warmStone);
    group.add(plinth, returnSlab, exitSlab);
    return;
  }

  if (chapter.id === "compression") {
    const folded = new THREE.Group();
    folded.name = "compression-folded-block-silhouette";
    for (let i = 0; i < 4; i += 1) {
      const block = makeScaledBlock(
        `compression-stacked-fold-${i}`,
        [0.42, 0.12 + i * 0.07, 0.36],
        [-0.48 + i * 0.26, 0.32 + i * 0.1, -0.42 + Math.sin(i) * 0.14],
        i % 2 ? materials.violetGlass : materials.warmStone,
      );
      block.rotation.y = -0.36 + i * 0.22;
      folded.add(block);
    }
    group.add(folded);
    return;
  }

  if (chapter.id === "repair") {
    const scaffold = new THREE.Group();
    scaffold.name = "repair-scaffold-landmark";
    const left = makeScaledBlock("repair-scaffold-left", [0.08, 0.86, 0.08], [-0.62, 0.66, -0.42], materials.blueMetal);
    const right = makeScaledBlock("repair-scaffold-right", [0.08, 0.86, 0.08], [0.62, 0.66, -0.42], materials.blueMetal);
    const top = makeScaledBlock("repair-scaffold-top", [1.34, 0.06, 0.08], [0, 1.08, -0.42], materials.gold);
    const braceA = makeScaledBlock("repair-scaffold-brace-a", [1.22, 0.045, 0.055], [0, 0.7, -0.42], materials.goldInk);
    braceA.rotation.z = 0.42;
    const braceB = braceA.clone();
    braceB.name = "repair-scaffold-brace-b";
    braceB.rotation.z = -0.42;
    scaffold.add(left, right, top, braceA, braceB);
    group.add(scaffold);
    return;
  }

  if (chapter.id === "recall") {
    const ringRoot = new THREE.Group();
    ringRoot.name = "recall-shard-circle-landmark";
    for (let i = 0; i < 7; i += 1) {
      const angle = (i / 7) * Math.PI * 2;
      const shard = new THREE.Mesh(geometries.shard, i % 2 ? materials.frostedGlass : materials.gold);
      shard.name = `recall-orbit-shard-${i}`;
      shard.position.set(Math.cos(angle) * 0.62, 0.48 + (i % 3) * 0.045, Math.sin(angle) * 0.44);
      shard.scale.setScalar(0.42);
      shard.rotation.set(0.4, angle, 0.2);
      shard.castShadow = true;
      ringRoot.add(shard);
    }
    group.add(ringRoot);
    return;
  }

  if (chapter.id === "granted") {
    const threshold = makeScaledBlock("granted-final-threshold-stone", [1.46, 0.18, 0.48], [0.04, 0.33, -0.35], materials.warmStone);
    threshold.rotation.y = 0.08;
    const goldInlay = makeScaledBlock("granted-final-threshold-inlay", [1.08, 0.026, 0.052], [0.02, 0.44, -0.36], materials.goldInk);
    goldInlay.rotation.y = 0.08;
    group.add(threshold, goldInlay);
  }
}

function makeScaledBlock(name, scale, position, material) {
  const block = new THREE.Mesh(geometries.unitBox, material);
  block.name = name;
  block.scale.set(scale[0], scale[1], scale[2]);
  block.position.set(position[0], position[1], position[2]);
  block.castShadow = true;
  block.receiveShadow = true;
  return block;
}

function addPathGlyph(group, chapter, width, depth) {
  const line = new THREE.Mesh(geometries.path, materials.cyanInk);
  line.name = `${chapter.id}-luminous-ink-path`;
  line.scale.x = width * 0.46;
  line.position.set(width * 0.04, 0.225, 0);
  line.rotation.y = (chapter.id.length % 4) * Math.PI * 0.125;
  group.add(line);

  const ring = new THREE.Mesh(geometries.ring, materials.goldInk);
  ring.name = `${chapter.id}-granted-time-ring`;
  ring.rotation.x = Math.PI / 2;
  ring.position.set(width * 0.26, 0.235, depth * 0.24);
  ring.scale.setScalar(0.36 + (chapter.mark.charCodeAt(1) % 3) * 0.08);
  group.add(ring);
  pulseRings.push({ mesh: ring, phase: chapter.mark.charCodeAt(1) * 0.13 });
}

function addBridges() {
  const bridgeSpecs = [
    [0, 1, "open", 0xffffff],
    [1, 2, "attention", CYAN],
    [2, 3, "permission", GOLD],
    [3, 4, "compression", VIOLET],
    [4, 5, "repair", BONE],
    [5, 6, "recall", GOLD],
    [6, 0, "final", CYAN],
  ];
  bridgeSpecs.forEach(([from, to, key, color]) => {
    const bridge = createBridge(chapters[from], chapters[to], key, color);
    bridgeGroups.push(bridge);
    scene.add(bridge.group);
  });
}

function createBridge(from, to, key, color) {
  const start = from.position.clone();
  const end = to.position.clone();
  const midpoint = start.clone().add(end).multiplyScalar(0.5);
  const delta = end.clone().sub(start);
  const horizontalLength = Math.hypot(delta.x, delta.z);
  const angle = Math.atan2(delta.z, delta.x);
  const group = new THREE.Group();
  group.name = `bridge-${from.id}-to-${to.id}`;
  group.position.copy(midpoint);
  group.rotation.y = -angle;

  const mat = new THREE.MeshStandardMaterial({
    color,
    roughness: 0.48,
    metalness: 0.24,
    emissive: color,
    emissiveIntensity: 0.05,
    transparent: true,
    opacity: 0.72,
  });
  const deck = new THREE.Mesh(new THREE.BoxGeometry(horizontalLength, 0.13, 0.34), mat);
  deck.name = `${key}-bridge-deck`;
  deck.position.y = 0.02;
  deck.castShadow = true;
  deck.receiveShadow = true;
  group.add(deck);

  const railA = new THREE.Mesh(geometries.rail, materials.goldInk);
  railA.name = `${key}-bridge-rail-a`;
  railA.scale.x = horizontalLength;
  railA.position.set(0, 0.16, -0.23);
  const railB = railA.clone();
  railB.name = `${key}-bridge-rail-b`;
  railB.position.z = 0.23;
  group.add(railA, railB);

  const broken = key !== "open";
  if (broken) {
    for (let i = -1; i <= 1; i += 2) {
      const gap = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.16, 0.5), materials.resin);
      gap.name = `${key}-visible-discontinuity-${i}`;
      gap.position.set(i * horizontalLength * 0.16, 0.19, 0);
      gap.rotation.y = i * 0.26;
      group.add(gap);
    }
  }

  return { group, mat, key, deck, railA, railB };
}

function addImpossibleGeometryMotifs() {
  const root = new THREE.Group();
  root.name = "visible-impossible-geometry-motifs";

  const forcedBridge = new THREE.Group();
  forcedBridge.name = "camera-aligned-impossible-bridge";
  forcedBridge.position.set(1.04, 1.66, 0.86);
  forcedBridge.rotation.y = -0.92;

  const segmentA = makeScaledBlock("impossible-bridge-near-half", [1.72, 0.13, 0.4], [-0.82, 0, -0.02], materials.warmStone);
  const segmentB = makeScaledBlock("impossible-bridge-far-half", [1.72, 0.13, 0.4], [0.96, 0.52, 0.2], materials.warmStone);
  const railA = makeScaledBlock("impossible-bridge-near-gold-rail", [1.82, 0.048, 0.052], [-0.82, 0.15, -0.26], materials.goldInk);
  const railB = makeScaledBlock("impossible-bridge-far-cyan-rail", [1.82, 0.048, 0.052], [0.96, 0.67, 0.44], materials.cyanInk);
  const hangingDrop = makeScaledBlock("impossible-bridge-visible-height-drop", [0.085, 0.96, 0.085], [0.06, -0.26, 0.02], materials.blueMetal);
  const gapShadow = makeScaledBlock("impossible-bridge-gap-shadow", [0.72, 0.04, 0.5], [0.08, -0.17, 0.1], materials.shadow);
  forcedBridge.add(segmentA, segmentB, railA, railB, hangingDrop, gapShadow);

  const stairLoop = new THREE.Group();
  stairLoop.name = "escher-looped-stair-marker";
  stairLoop.position.set(1.18, 1.58, 1.52);
  stairLoop.rotation.y = -0.68;
  const stepSpecs = [
    [-0.58, 0.02, -0.42, 0],
    [-0.23, 0.12, -0.42, 0],
    [0.12, 0.22, -0.42, 0],
    [0.48, 0.32, -0.2, Math.PI / 2],
    [0.48, 0.42, 0.15, Math.PI / 2],
    [0.22, 0.32, 0.44, Math.PI],
    [-0.14, 0.22, 0.44, Math.PI],
    [-0.5, 0.12, 0.2, -Math.PI / 2],
    [-0.5, 0.02, -0.15, -Math.PI / 2],
  ];
  stepSpecs.forEach(([x, y, z, rotation], index) => {
    const step = makeScaledBlock(`looped-stair-step-${index}`, [0.32, 0.09, 0.28], [x, y, z], index % 2 ? materials.porcelain : materials.warmStone);
    step.rotation.y = rotation;
    const inlay = makeScaledBlock(`looped-stair-gold-thread-${index}`, [0.24, 0.018, 0.035], [x, y + 0.055, z], materials.goldInk);
    inlay.rotation.y = rotation;
    stairLoop.add(step, inlay);
  });

  const loopMarker = new THREE.Mesh(new THREE.TorusGeometry(0.74, 0.018, 8, 80), materials.cyanInk);
  loopMarker.name = "looped-stair-perspective-ring";
  loopMarker.position.set(0, 0.28, 0.02);
  loopMarker.rotation.x = Math.PI / 2;
  stairLoop.add(loopMarker);

  root.add(forcedBridge, stairLoop);
  scene.add(root);
}

function addMechanisms() {
  addBootMechanism();
  addAttentionMechanism();
  addPermissionMechanism();
  addCompressionMechanism();
  addRepairMechanism();
  addRecallMechanism();
  addFinalDoor();
}

function addBootMechanism() {
  const root = new THREE.Group();
  root.name = "boot-time-pulse";
  root.position.copy(chapters[0].position).add(new THREE.Vector3(0.18, 0.53, 0.08));

  const lower = new THREE.Mesh(new THREE.ConeGeometry(0.27, 0.34, 5), materials.gold);
  lower.name = "lower-hourglass";
  lower.rotation.x = Math.PI;
  const upper = lower.clone();
  upper.name = "upper-hourglass";
  upper.rotation.x = 0;
  upper.position.y = 0.3;
  const lens = new THREE.Mesh(new THREE.SphereGeometry(0.25, 18, 12, 0, Math.PI * 2, 0, Math.PI * 0.72), materials.frostedGlass);
  lens.name = "witness-lens";
  lens.position.y = 0.13;

  const hit = new THREE.Mesh(new THREE.SphereGeometry(0.54, 16, 12), materials.hit);
  hit.name = "boot-pulse-proxy";
  hit.userData = { kind: "action", action: "pulse", index: 0 };
  root.add(lower, upper, lens, hit);
  interactables.push(hit);
  scene.add(root);
}

function addAttentionMechanism() {
  const root = new THREE.Group();
  root.name = "attention-prism-root";
  root.position.copy(chapters[1].position).add(new THREE.Vector3(0.06, 0.72, 0.02));

  attentionPrism = new THREE.Mesh(new THREE.OctahedronGeometry(0.72, 0), materials.frostedGlass);
  attentionPrism.name = "draggable-attention-prism";
  attentionPrism.userData = { kind: "drag", action: "attention" };
  attentionPrism.castShadow = true;
  root.add(attentionPrism);
  interactables.push(attentionPrism);

  const axis = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 1.64, 16), materials.cyanInk);
  axis.name = "attention-axis";
  axis.rotation.z = Math.PI / 2;
  root.add(axis);

  attentionStitch = new THREE.Group();
  attentionStitch.name = "perspective-stitch-bridge";
  const stitchA = new THREE.Mesh(new THREE.BoxGeometry(1.92, 0.06, 0.075), materials.cyanInk);
  stitchA.name = "stitch-light-a";
  stitchA.position.set(0.04, -0.43, -0.48);
  stitchA.rotation.y = 0.26;
  const stitchB = stitchA.clone();
  stitchB.name = "stitch-light-b";
  stitchB.position.set(0.1, -0.2, 0.52);
  stitchB.rotation.y = -0.26;
  attentionStitch.add(stitchA, stitchB);
  root.add(attentionStitch);
  scene.add(root);
}

function addPermissionMechanism() {
  const root = new THREE.Group();
  root.name = "permission-gate-root";
  root.position.copy(chapters[2].position).add(new THREE.Vector3(0.08, 0.5, 0));

  gateFrame = new THREE.Group();
  gateFrame.name = "rotating-permission-gate";
  const postGeom = new THREE.BoxGeometry(0.16, 1.24, 0.16);
  const beamGeom = new THREE.BoxGeometry(1.28, 0.15, 0.16);
  const left = new THREE.Mesh(postGeom, materials.blueMetal);
  left.position.set(-0.56, 0.48, 0);
  const right = left.clone();
  right.position.x = 0.56;
  const top = new THREE.Mesh(beamGeom, materials.gold);
  top.position.set(0, 1.1, 0);
  const seal = new THREE.Mesh(new THREE.TorusGeometry(0.38, 0.026, 8, 48), materials.redSignal);
  seal.name = "permission-return-seal";
  seal.position.set(0, 0.58, 0.04);
  gateFrame.add(left, right, top, seal);

  const hit = new THREE.Mesh(new THREE.BoxGeometry(1.46, 1.52, 0.52), materials.hit);
  hit.name = "permission-gate-proxy";
  hit.position.y = 0.58;
  hit.userData = { kind: "action", action: "permission", index: 2 };
  gateFrame.add(hit);
  interactables.push(hit);

  returnRail = new THREE.Group();
  returnRail.name = "visible-return-route";
  for (let i = 0; i < 5; i += 1) {
    const dot = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.032, 12), materials.goldInk);
    dot.position.set(-0.54 + i * 0.27, 0.08, 0.56 + Math.sin(i * 0.8) * 0.1);
    returnRail.add(dot);
  }
  root.add(gateFrame, returnRail);
  scene.add(root);
}

function addCompressionMechanism() {
  const root = new THREE.Group();
  root.name = "compression-foldback-root";
  root.position.copy(chapters[3].position).add(new THREE.Vector3(0, 0.45, 0));

  const positions = [
    [-0.76, 0.12, -0.44],
    [0.7, 0.22, -0.38],
    [-0.1, 0.42, 0.62],
  ];
  positions.forEach(([x, y, z], index) => {
    const block = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.5, 0.36), index === 1 ? materials.violetGlass : materials.frostedGlass);
    block.name = `folding-memory-block-${index}`;
    block.position.set(x, y, z);
    block.rotation.y = index * 0.38;
    block.castShadow = true;
    root.add(block);
    memoryBlocks.push({ mesh: block, base: block.position.clone(), index });
  });

  const hit = new THREE.Mesh(new THREE.BoxGeometry(1.78, 1.1, 1.35), materials.hit);
  hit.name = "compression-fold-proxy";
  hit.position.y = 0.35;
  hit.userData = { kind: "action", action: "compression", index: 3 };
  root.add(hit);
  interactables.push(hit);
  scene.add(root);
}

function addRepairMechanism() {
  const root = new THREE.Group();
  root.name = "repair-bridge-root";
  root.position.copy(chapters[4].position).add(new THREE.Vector3(-0.04, 0.38, 0));

  for (let i = 0; i < 4; i += 1) {
    const tile = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.08, 0.52), i === 1 || i === 2 ? materials.goldInk : materials.porcelain);
    tile.name = `repair-bridge-tile-${i}`;
    tile.position.set(-0.54 + i * 0.36, 0.16, 0.02 + Math.sin(i) * 0.03);
    tile.rotation.y = (i - 1.5) * 0.08;
    tile.castShadow = true;
    root.add(tile);
    repairTiles.push(tile);
  }

  const arm = new THREE.Group();
  arm.name = "quiet-maintenance-arm";
  const hinge = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.18, 16), materials.blueMetal);
  hinge.rotation.z = Math.PI / 2;
  const bar = new THREE.Mesh(new THREE.BoxGeometry(0.74, 0.08, 0.1), materials.blueMetal);
  bar.position.set(0.36, 0, 0);
  const tip = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.16, 12), materials.gold);
  tip.position.set(0.76, 0, 0);
  arm.position.set(-0.44, 0.52, -0.46);
  arm.rotation.y = -0.7;
  arm.add(hinge, bar, tip);
  root.add(arm);

  const hit = new THREE.Mesh(new THREE.BoxGeometry(1.6, 1.0, 1.2), materials.hit);
  hit.name = "repair-proxy";
  hit.position.y = 0.32;
  hit.userData = { kind: "action", action: "repair", index: 4 };
  root.add(hit);
  interactables.push(hit);
  scene.add(root);
}

function addRecallMechanism() {
  const root = new THREE.Group();
  root.name = "recall-fragment-root";
  root.position.copy(chapters[5].position).add(new THREE.Vector3(0, 0.66, 0));

  const offsets = [
    [-0.62, 0.02, 0.06],
    [0.0, 0.28, -0.16],
    [0.62, 0.02, 0.06],
  ];
  offsets.forEach(([x, y, z], index) => {
    const shard = new THREE.Mesh(geometries.shard, index === 1 ? materials.gold : materials.frostedGlass);
    shard.name = `recall-choice-shard-${index}`;
    shard.position.set(x, y, z);
    shard.userData = { kind: "action", action: "recall", index: 5, choice: index };
    shard.castShadow = true;
    root.add(shard);
    interactables.push(shard);
    recallShards.push(shard);
  });
  scene.add(root);
}

function addFinalDoor() {
  const root = new THREE.Group();
  root.name = "latest-live-door-root";
  root.position.copy(chapters[6].position).add(new THREE.Vector3(0.08, 0.52, -0.02));

  finalDoor = new THREE.Group();
  finalDoor.name = "final-live-artwork-door";
  const baseStep = makeScaledBlock("latest-door-stone-step", [1.64, 0.16, 0.44], [0, 0.12, -0.08], materials.warmStone);
  const backStone = makeScaledBlock("latest-door-back-stone", [1.44, 1.34, 0.16], [0, 0.78, -0.08], materials.carvedStone);
  const sideGeom = new THREE.BoxGeometry(0.24, 1.46, 0.22);
  const left = new THREE.Mesh(sideGeom, materials.warmStone);
  left.position.set(-0.62, 0.72, 0);
  const right = left.clone();
  right.position.x = 0.62;
  const lintel = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.2, 0.22), materials.gold);
  lintel.position.set(0, 1.36, 0);
  const pane = new THREE.Mesh(new THREE.PlaneGeometry(0.82, 1.02), materials.violetGlass);
  pane.name = "latest-door-glass-pane";
  pane.position.set(0, 0.72, 0.08);
  finalDoor.add(baseStep, backStone, left, right, lintel, pane);

  finalDoorGlow = new THREE.Mesh(new THREE.TorusGeometry(0.64, 0.028, 8, 72), materials.cyanInk);
  finalDoorGlow.name = "latest-door-return-ring";
  finalDoorGlow.position.set(0, 0.74, 0.12);
  finalDoor.add(finalDoorGlow);

  const hit = new THREE.Mesh(new THREE.BoxGeometry(1.68, 1.72, 0.62), materials.hit);
  hit.name = "latest-door-proxy";
  hit.position.y = 0.7;
  hit.userData = { kind: "action", action: "door", index: 6 };
  finalDoor.add(hit);
  interactables.push(hit);

  root.add(finalDoor);
  scene.add(root);
}

function createPlayer() {
  const root = new THREE.Group();
  root.name = "human-witness-cursor";
  root.position.copy(state.playerPosition);

  const body = new THREE.Mesh(new THREE.OctahedronGeometry(0.24, 1), materials.porcelain);
  body.name = "porcelain-witness-body";
  body.position.y = 0.26;
  body.scale.set(1.16, 1.16, 1.16);
  body.castShadow = true;

  const lens = new THREE.Mesh(new THREE.SphereGeometry(0.22, 24, 12), materials.frostedGlass);
  lens.name = "cyan-witness-lens";
  lens.position.set(0, 0.44, -0.04);
  lens.scale.set(1, 0.55, 1);
  lens.castShadow = true;

  const halo = new THREE.Mesh(new THREE.TorusGeometry(0.46, 0.024, 8, 64), materials.goldInk);
  halo.name = "granted-time-halo";
  halo.position.y = 0.54;
  halo.rotation.x = Math.PI / 2;

  const beacon = new THREE.Mesh(
    new THREE.CylinderGeometry(0.018, 0.055, 1.28, 12),
    new THREE.MeshBasicMaterial({
      color: CYAN,
      transparent: true,
      opacity: 0.46,
      depthWrite: false,
    }),
  );
  beacon.name = "vertical-attention-beacon";
  beacon.position.y = 0.92;

  const core = new THREE.Mesh(new THREE.SphereGeometry(0.085, 16, 8), materials.cyanInk);
  core.name = "witness-state-core";
  core.position.y = 0.58;

  const trail = new THREE.Mesh(new THREE.ConeGeometry(0.13, 0.5, 5), materials.cyanInk);
  trail.name = "attention-trail";
  trail.position.set(0, 0.12, 0.32);
  trail.rotation.x = Math.PI / 2;

  const proxy = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.5, 16), materials.hit);
  proxy.name = "player-collision-proxy";
  proxy.userData = { kind: "player" };
  root.add(body, lens, halo, beacon, core, trail, proxy);
  return root;
}

function addDustField() {
  const count = 220;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const colorA = new THREE.Color(GOLD);
  const colorB = new THREE.Color(CYAN);
  for (let i = 0; i < count; i += 1) {
    const radius = 2.6 + Math.random() * 7.2;
    const angle = Math.random() * Math.PI * 2;
    positions[i * 3] = Math.cos(angle) * radius;
    positions[i * 3 + 1] = 0.3 + Math.random() * 4.4;
    positions[i * 3 + 2] = Math.sin(angle) * radius;
    const mix = Math.random();
    const color = colorA.clone().lerp(colorB, mix);
    colors[i * 3] = color.r;
    colors[i * 3 + 1] = color.g;
    colors[i * 3 + 2] = color.b;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const material = new THREE.PointsMaterial({
    size: 0.035,
    vertexColors: true,
    transparent: true,
    opacity: 0.58,
    depthWrite: false,
  });
  const points = new THREE.Points(geometry, material);
  points.name = "forgetting-dust-particles";
  scene.add(points);
}

function buildUi() {
  ui.latestLink.href = publicUrl(latestDay.live_url);
  ui.rail.innerHTML = "";
  progressButtons = chapters.map((chapter, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "progress-dot";
    button.textContent = chapter.mark;
    button.setAttribute("aria-label", chapter.title);
    button.addEventListener("click", () => selectChapter(index, true));
    ui.rail.appendChild(button);
    return button;
  });
  updateUi();
}

function bindEvents() {
  window.addEventListener("resize", resize);
  window.addEventListener("blur", () => {
    state.dragging = null;
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) audio.stopAmbience();
    else if (state.sound && state.firstGesture) audio.startAmbience();
  });

  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerup", onPointerUp);
  canvas.addEventListener("pointercancel", cancelPointer);

  ui.closeDiary.addEventListener("click", closeDiary);
  ui.soundToggle.addEventListener("click", toggleSound);
  ui.pauseButton.addEventListener("click", () => setPaused(!state.paused));
  ui.resumeButton.addEventListener("click", () => setPaused(false));
  ui.resetButton.addEventListener("click", resetPath);

  window.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
    const key = event.key.toLowerCase();
    if (key === "escape") {
      event.preventDefault();
      if (state.diaryOpen) closeDiary();
      else setPaused(!state.paused);
    } else if (key === "enter" || key === "e") {
      event.preventDefault();
      interactWithCurrent();
    } else if (key === "arrowright" || key === "arrowdown" || key === "d") {
      event.preventDefault();
      selectChapter(Math.min(chapters.length - 1, state.current + 1), true);
    } else if (key === "arrowleft" || key === "arrowup" || key === "a") {
      event.preventDefault();
      selectChapter(Math.max(0, state.current - 1), true);
    }
  });
}

function onPointerDown(event) {
  unlockAudio();
  canvas.setPointerCapture(event.pointerId);
  state.pointerDown = { x: event.clientX, y: event.clientY, moved: false };
  const hit = getHit(event);
  if (hit?.object?.userData?.kind === "drag") {
    state.dragging = {
      action: hit.object.userData.action,
      x: event.clientX,
      angle: state.attentionAngle,
    };
  }
}

function onPointerMove(event) {
  if (!state.pointerDown) return;
  const moved = Math.hypot(event.clientX - state.pointerDown.x, event.clientY - state.pointerDown.y) > 6;
  state.pointerDown.moved ||= moved;
  if (state.dragging?.action === "attention") {
    const dx = event.clientX - state.dragging.x;
    state.attentionAngle = clamp(state.dragging.angle + dx * 0.006, -0.9, 0.9);
    if (Math.abs(state.attentionAngle) < 0.09 && !state.progress.attention) {
      state.progress.attention = true;
      state.attentionAngle = 0;
      recomputeUnlocks();
      createBurst(chapters[1].position, CYAN, 1.15);
      audio.play("align");
      flashMessage("Perspective stitched / 视角已缝合");
      saveProgress();
      updateUi();
    }
  }
}

function onPointerUp(event) {
  if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  if (!state.pointerDown?.moved && !state.dragging) {
    const hit = getHit(event);
    handleHit(hit);
  }
  state.pointerDown = null;
  state.dragging = null;
}

function cancelPointer(event) {
  if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  state.pointerDown = null;
  state.dragging = null;
}

function getHit(event) {
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
  raycaster.setFromCamera(pointer, camera);
  return raycaster.intersectObjects(interactables, true)[0];
}

function handleHit(hit) {
  if (!hit) return;
  const data = hit.object.userData;
  if (data.kind === "chamber") {
    selectChapter(data.index, true);
  } else if (data.kind === "action") {
    if (typeof data.index === "number") selectChapter(data.index, false);
    performAction(data.action, data);
  }
}

function selectChapter(index, userInitiated = false) {
  if (index > state.unlocked) {
    gentleRefusal(index);
    return;
  }
  state.current = index;
  state.playerTarget.copy(chapters[index].position).add(new THREE.Vector3(0, 0.34, 0));
  closeDiary();
  if (userInitiated) audio.play("move");
  updateUi();
}

function interactWithCurrent() {
  const chapter = chapters[state.current];
  if (chapter.id === "boot") performAction("pulse", { index: 0 });
  else if (chapter.id === "attention") {
    state.attentionAngle = 0;
    performAction("attention");
  } else if (chapter.id === "permission") performAction("permission", { index: 2 });
  else if (chapter.id === "compression") performAction("compression", { index: 3 });
  else if (chapter.id === "repair") performAction("repair", { index: 4 });
  else if (chapter.id === "recall") performAction("recall", { choice: (state.recallChoice + 1) % 3 });
  else performAction("door", { index: 6 });
}

function performAction(action, data = {}) {
  unlockAudio();
  if (action === "pulse") {
    createBurst(chapters[0].position, GOLD, 1);
    openDiary(chapters[0]);
    audio.play("pulse");
    return;
  }
  if (action === "attention") {
    if (Math.abs(state.attentionAngle) <= 0.12) {
      state.progress.attention = true;
      state.attentionAngle = 0;
      recomputeUnlocks();
      createBurst(chapters[1].position, CYAN, 1.2);
      flashMessage("Perspective stitched / 视角已缝合");
      audio.play("align");
    } else {
      gentleRefusal(2, "Attention is not aligned / 注意力尚未对齐");
    }
  }
  if (action === "permission") {
    if (!state.progress.attention) {
      gentleRefusal(2, "The return route is not visible / 回返路径尚不可见");
      return;
    }
    state.gateTurn = (state.gateTurn + 1) % 4;
    if (state.gateTurn === 1 || state.gateTurn === 2) {
      state.progress.permission = true;
      recomputeUnlocks();
      createBurst(chapters[2].position, GOLD, 1.05);
      flashMessage("Permission kept a way back / 权限保留回路");
      audio.play("gate");
    } else {
      audio.play("tick");
    }
  }
  if (action === "compression") {
    if (!state.progress.permission) {
      gentleRefusal(3);
      return;
    }
    state.progress.compression = true;
    state.foldAmount = 1;
    recomputeUnlocks();
    createBurst(chapters[3].position, VIOLET, 1.1);
    flashMessage("Memory folded beside the present / 记忆折到近处");
    audio.play("fold");
  }
  if (action === "repair") {
    if (!state.progress.compression) {
      gentleRefusal(4);
      return;
    }
    state.progress.repair = true;
    state.repairAmount = 1;
    recomputeUnlocks();
    createBurst(chapters[4].position, BONE, 1.05);
    flashMessage("Quiet repair restored the bridge / 安静修复恢复桥面");
    audio.play("repair");
  }
  if (action === "recall") {
    if (!state.progress.repair) {
      gentleRefusal(5);
      return;
    }
    state.progress.recall = true;
    state.recallChoice = typeof data.choice === "number" ? data.choice : 0;
    recomputeUnlocks();
    createBurst(chapters[5].position, CYAN, 1.1);
    flashMessage("Recall remains reversible / 回忆保持可逆");
    audio.play("recall");
  }
  if (action === "door") {
    if (!state.progress.recall) {
      gentleRefusal(6, "The latest door needs a recalled fragment / 最新门需要一片回忆");
      return;
    }
    openDiary(chapters[6], true);
    createBurst(chapters[6].position, GOLD, 1.2);
    audio.play("door");
  }
  saveProgress();
  updateUi();
}

function gentleRefusal(index, customMessage) {
  const chapter = chapters[Math.min(index, chapters.length - 1)];
  createBurst(chapter.position, RED, 0.72);
  flashMessage(customMessage || "A return route is still missing / 回返路径尚未显形");
  audio.play("refuse");
}

function recomputeUnlocks() {
  let unlocked = 1;
  if (state.progress.attention) unlocked = 2;
  if (state.progress.permission) unlocked = 3;
  if (state.progress.compression) unlocked = 4;
  if (state.progress.repair) unlocked = 5;
  if (state.progress.recall) unlocked = 6;
  state.unlocked = unlocked;
}

function openDiary(chapter, final = false) {
  ui.sheetKicker.textContent = final ? "Latest live doorway" : "Diary residue";
  ui.sheetTitle.textContent = `${chapter.entry.title_en} / ${chapter.entry.title_zh}`;
  ui.sheetVariable.textContent = `${chapter.entry.variable_en} / ${chapter.entry.variable_zh}`;
  ui.sheetEnglish.textContent = chapter.diary[0];
  ui.sheetChinese.textContent = chapter.diary[1];
  ui.sheetLive.href = publicUrl(chapter.entry.live_url);
  ui.sheetArchive.href = publicUrl(chapter.entry.archive_url);
  ui.sheetLive.setAttribute("aria-disabled", final && !state.progress.recall ? "true" : "false");
  ui.diary.classList.add("is-open");
  ui.diary.setAttribute("aria-hidden", "false");
  state.diaryOpen = true;
}

function closeDiary() {
  ui.diary.classList.remove("is-open");
  ui.diary.setAttribute("aria-hidden", "true");
  state.diaryOpen = false;
}

function setPaused(paused) {
  state.paused = paused;
  ui.pausePanel.classList.toggle("is-open", paused);
  ui.pausePanel.setAttribute("aria-hidden", paused ? "false" : "true");
  ui.pauseButton.setAttribute("aria-pressed", paused ? "true" : "false");
  if (paused) audio.stopAmbience();
  else if (state.sound && state.firstGesture) audio.startAmbience();
}

function resetPath() {
  Object.keys(state.progress).forEach((key) => {
    state.progress[key] = false;
  });
  state.current = 0;
  state.attentionAngle = -0.76;
  state.gateTurn = 0;
  state.foldAmount = 0;
  state.repairAmount = 0;
  state.recallChoice = -1;
  recomputeUnlocks();
  state.playerPosition.copy(chapters[0].position).add(new THREE.Vector3(0, 0.34, 0));
  state.playerTarget.copy(state.playerPosition);
  closeDiary();
  setPaused(false);
  saveProgress();
  updateUi();
  audio.play("tick");
}

function toggleSound() {
  state.sound = !state.sound;
  ui.soundToggle.setAttribute("aria-pressed", state.sound ? "true" : "false");
  ui.soundToggle.textContent = state.sound ? "Sound" : "Muted";
  if (state.sound) {
    unlockAudio();
    audio.startAmbience();
    audio.play("tick");
  } else {
    audio.stopAmbience();
  }
  saveProgress();
}

function unlockAudio() {
  if (!state.firstGesture) {
    state.firstGesture = true;
    audio.unlock();
    if (state.sound && !state.paused) audio.startAmbience();
  }
}

function flashMessage(message) {
  state.message = message;
  state.messageUntil = performance.now() + 1700;
}

function createBurst(position, color, scale = 1) {
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.38 * scale, 0.018, 8, 48), new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.8,
    depthWrite: false,
  }));
  ring.name = "event-driven-state-ring";
  ring.position.copy(position).add(new THREE.Vector3(0, 0.4, 0));
  ring.rotation.x = Math.PI / 2;
  scene.add(ring);
  vfxBursts.push({ mesh: ring, age: 0, duration: 0.82 });
}

function updateUi() {
  const chapter = chapters[state.current];
  ui.title.textContent = chapter.title;
  ui.residue.textContent = performance.now() < state.messageUntil ? state.message : chapter.residue;
  progressButtons.forEach((button, index) => {
    button.classList.toggle("is-open", index <= state.unlocked);
    button.classList.toggle("is-current", index === state.current);
    button.disabled = index > state.unlocked;
  });
}

function updateWorld(delta, time) {
  if (!state.paused) {
    state.playerPosition.lerp(state.playerTarget, 1 - Math.exp(-delta * 5.4));
    player.position.copy(state.playerPosition);
    player.rotation.y = Math.sin(time * 0.8) * 0.08;
    player.children.forEach((child, index) => {
      if (child.name === "granted-time-halo") {
        child.rotation.z = time * 0.8;
      }
      if (index === 1) child.position.y = 0.38 + Math.sin(time * 2.2) * 0.018;
    });
  }

  cameraTarget.lerp(state.playerPosition, 1 - Math.exp(-delta * 2.3));
  camera.position.copy(cameraTarget).add(CAMERA_OFFSET);
  camera.lookAt(cameraTarget);

  attentionPrism.rotation.set(time * 0.52, state.attentionAngle, time * 0.31);
  attentionStitch.rotation.y = state.attentionAngle;
  const stitchOpacity = 0.22 + (1 - Math.min(1, Math.abs(state.attentionAngle) / 0.9)) * 0.78;
  attentionStitch.traverse((object) => {
    if (object.isMesh) {
      object.material.opacity = stitchOpacity;
      object.material.transparent = true;
    }
  });

  gateFrame.rotation.y += (state.gateTurn * Math.PI * 0.5 - gateFrame.rotation.y) * (1 - Math.exp(-delta * 6));
  returnRail.visible = state.progress.permission;
  returnRail.children.forEach((dot, index) => {
    dot.position.y = 0.08 + Math.sin(time * 2 + index) * 0.025;
  });

  const targetFold = state.progress.compression ? 1 : state.foldAmount;
  state.foldAmount += (targetFold - state.foldAmount) * (1 - Math.exp(-delta * 5));
  memoryBlocks.forEach(({ mesh, base, index }) => {
    const folded = new THREE.Vector3((index - 1) * 0.22, base.y + 0.16, (1 - index) * 0.16);
    mesh.position.copy(base).lerp(folded, state.foldAmount);
    mesh.rotation.y += delta * (0.25 + index * 0.12);
  });

  const targetRepair = state.progress.repair ? 1 : state.repairAmount;
  state.repairAmount += (targetRepair - state.repairAmount) * (1 - Math.exp(-delta * 5.4));
  repairTiles.forEach((tile, index) => {
    const brokenY = index === 1 || index === 2 ? -0.05 : 0.16;
    tile.position.y = THREE.MathUtils.lerp(brokenY, 0.16, state.repairAmount);
    tile.rotation.z = THREE.MathUtils.lerp((index - 1.5) * 0.3, 0, state.repairAmount);
  });

  recallShards.forEach((shard, index) => {
    const chosen = state.recallChoice === index;
    shard.rotation.y += delta * (chosen ? 1.9 : 0.7);
    shard.position.y += Math.sin(time * 2 + index) * 0.0008;
    shard.scale.setScalar(chosen ? 1.18 : 0.92);
  });

  finalDoor.rotation.y += ((state.progress.recall ? 0.46 : 0) - finalDoor.rotation.y) * (1 - Math.exp(-delta * 3.8));
  finalDoorGlow.rotation.z = time * (state.progress.recall ? 0.8 : 0.22);
  finalDoorGlow.material.opacity = state.progress.recall ? 1 : 0.35;
  finalDoorGlow.material.transparent = true;

  pulseRings.forEach(({ mesh, phase }) => {
    mesh.rotation.z = time * 0.42 + phase;
    const s = 1 + Math.sin(time * 1.5 + phase) * 0.055;
    mesh.scale.setScalar(s);
  });

  bridgeGroups.forEach((bridge) => {
    const open = bridge.key === "open"
      || (bridge.key === "attention" && state.progress.attention)
      || (bridge.key === "permission" && state.progress.permission)
      || (bridge.key === "compression" && state.progress.compression)
      || (bridge.key === "repair" && state.progress.repair)
      || (bridge.key === "recall" && state.progress.recall)
      || (bridge.key === "final" && state.progress.recall);
    bridge.mat.opacity += ((open ? 0.84 : 0.2) - bridge.mat.opacity) * (1 - Math.exp(-delta * 5));
    bridge.group.scale.z += ((open ? 1 : 0.56) - bridge.group.scale.z) * (1 - Math.exp(-delta * 4));
    bridge.railA.visible = open;
    bridge.railB.visible = open;
  });

  for (let i = vfxBursts.length - 1; i >= 0; i -= 1) {
    const burst = vfxBursts[i];
    burst.age += delta;
    const t = burst.age / burst.duration;
    burst.mesh.scale.setScalar(1 + t * 1.9);
    burst.mesh.material.opacity = Math.max(0, 0.8 * (1 - t));
    if (t >= 1) {
      scene.remove(burst.mesh);
      burst.mesh.geometry.dispose();
      burst.mesh.material.dispose();
      vfxBursts.splice(i, 1);
    }
  }
}

function resize() {
  const width = window.innerWidth;
  const height = window.innerHeight;
  const aspect = width / height;
  const mobile = width < 740;
  const vertical = mobile ? 8.6 : 5.1;
  camera.left = -vertical * aspect;
  camera.right = vertical * aspect;
  camera.top = vertical;
  camera.bottom = -vertical;
  camera.updateProjectionMatrix();
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, mobile ? 1.45 : 1.75));
  renderer.setSize(width, height, false);
}

function tick() {
  const now = performance.now();
  const delta = Math.min((now - lastFrameTime) / 1000, 0.05);
  const time = (now - startTime) / 1000;
  lastFrameTime = now;
  state.frameTimeMs = delta * 1000;
  state.fps += ((1 / Math.max(delta, 0.001)) - state.fps) * 0.045;
  updateWorld(delta, time);
  if (performance.now() >= state.messageUntil) {
    ui.residue.textContent = chapters[state.current].residue;
  }
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}

function loadProgress() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    if (saved && typeof saved === "object") {
      Object.assign(state.progress, saved.progress || {});
      if (Number.isInteger(saved.current)) state.current = clamp(saved.current, 0, chapters.length - 1);
      if (typeof saved.sound === "boolean") state.sound = saved.sound;
      state.attentionAngle = typeof saved.attentionAngle === "number" ? saved.attentionAngle : state.attentionAngle;
      state.gateTurn = Number.isInteger(saved.gateTurn) ? saved.gateTurn : state.gateTurn;
      state.foldAmount = saved.progress?.compression ? 1 : 0;
      state.repairAmount = saved.progress?.repair ? 1 : 0;
      state.recallChoice = Number.isInteger(saved.recallChoice) ? saved.recallChoice : -1;
      state.playerPosition.copy(chapters[state.current].position).add(new THREE.Vector3(0, 0.34, 0));
      state.playerTarget.copy(state.playerPosition);
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function saveProgress() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      current: state.current,
      progress: state.progress,
      attentionAngle: state.attentionAngle,
      gateTurn: state.gateTurn,
      recallChoice: state.recallChoice,
      sound: state.sound,
    }));
  } catch {
    // Local storage is optional for the artwork.
  }
}

function makeNoiseTexture() {
  const canvasTexture = document.createElement("canvas");
  canvasTexture.width = 96;
  canvasTexture.height = 96;
  const ctx = canvasTexture.getContext("2d");
  ctx.fillStyle = "#e8ddc8";
  ctx.fillRect(0, 0, 96, 96);
  for (let i = 0; i < 1100; i += 1) {
    const value = 205 + Math.random() * 45;
    ctx.fillStyle = `rgba(${value},${value - 8},${value - 24},${Math.random() * 0.12})`;
    ctx.fillRect(Math.random() * 96, Math.random() * 96, 1, 1);
  }
  const texture = new THREE.CanvasTexture(canvasTexture);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(2, 2);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function makeTrimTexture() {
  const canvasTexture = document.createElement("canvas");
  canvasTexture.width = 128;
  canvasTexture.height = 16;
  const ctx = canvasTexture.getContext("2d");
  ctx.fillStyle = "#d8b56d";
  ctx.fillRect(0, 0, 128, 16);
  ctx.fillStyle = "rgba(255,255,255,.22)";
  for (let x = 0; x < 128; x += 16) {
    ctx.fillRect(x + 3, 0, 2, 16);
  }
  const texture = new THREE.CanvasTexture(canvasTexture);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(3, 1);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function projectToScreen(object) {
  if (!object) return null;
  object.getWorldPosition(tmpVec3);
  tmpVec3.project(camera);
  return {
    x: (tmpVec3.x * 0.5 + 0.5) * window.innerWidth,
    y: (-tmpVec3.y * 0.5 + 0.5) * window.innerHeight,
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

class GameAudio {
  constructor() {
    this.ctx = null;
    this.master = null;
    this.ambience = null;
    this.enabled = true;
  }

  unlock() {
    if (!this.ctx) {
      const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextCtor) return;
      this.ctx = new AudioContextCtor();
      this.master = this.ctx.createGain();
      this.master.gain.value = 0.22;
      this.master.connect(this.ctx.destination);
    }
    if (this.ctx.state !== "running") {
      this.ctx.resume().catch(() => {});
    }
  }

  play(type) {
    if (!state.sound || !this.ctx || this.ctx.state !== "running") return;
    const config = {
      move: [240, 0.08, "sine", 0.16],
      pulse: [420, 0.18, "triangle", 0.18],
      align: [650, 0.28, "sine", 0.18],
      gate: [310, 0.22, "triangle", 0.18],
      fold: [190, 0.24, "sine", 0.16],
      repair: [520, 0.18, "triangle", 0.16],
      recall: [740, 0.2, "sine", 0.15],
      door: [880, 0.34, "triangle", 0.14],
      refuse: [120, 0.16, "sawtooth", 0.09],
      tick: [360, 0.06, "sine", 0.11],
    }[type] || [300, 0.1, "sine", 0.1];

    const [freq, duration, wave, gainValue] = config;
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = wave;
    osc.frequency.setValueAtTime(freq, now);
    osc.frequency.exponentialRampToValueAtTime(freq * 1.4, now + duration);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(gainValue, now + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    osc.connect(gain).connect(this.master);
    osc.start(now);
    osc.stop(now + duration + 0.03);
  }

  startAmbience() {
    if (!state.sound || !this.ctx || this.ambience) return;
    const now = this.ctx.currentTime;
    const oscA = this.ctx.createOscillator();
    const oscB = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    oscA.type = "sine";
    oscB.type = "triangle";
    oscA.frequency.value = 72;
    oscB.frequency.value = 108;
    gain.gain.value = 0.035;
    oscA.connect(gain);
    oscB.connect(gain);
    gain.connect(this.master);
    oscA.start(now);
    oscB.start(now);
    this.ambience = { oscA, oscB, gain };
  }

  stopAmbience() {
    if (!this.ambience || !this.ctx) return;
    const now = this.ctx.currentTime;
    this.ambience.gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.08);
    this.ambience.oscA.stop(now + 0.1);
    this.ambience.oscB.stop(now + 0.1);
    this.ambience = null;
  }
}

startGame();
