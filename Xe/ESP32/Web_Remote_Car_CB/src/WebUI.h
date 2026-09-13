#pragma once

static const char* WEB_PAGE = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>ESP32 Car Control</title>

<style>
:root{
  --font-family: Arial, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  --c-bg:#f5f7fb; --c-card-bd:#e2e8f0; --c-track:#d7dee8; --c-switch-off:#bbb; --c-switch-on:#22c55e;
  --c-thumb-1:#2563eb; --c-thumb-2:#10b981; --c-text:#333;
  --radius-card:18px; --shadow-card:0 8px 22px rgba(0,0,0,.08); --shadow-thumb:0 2px 6px rgba(0,0,0,.25);
  --slider-track-h:8px;
  --thumb-vert-w:80px; --thumb-vert-h:80px; --thumb-horz-w:80px; --thumb-horz-h:80px;
  --sw-w: 7.2vw; --sw-h: 3.4vw; --sw-pad: 0.25vw;
  --container-max-w: 1000px; --col-gap: 2vw;
  --rect-pad: 1.2vw; --rect-vert-w: 12vw; --rect-vert-min-w: 120px; --rect-vert-h: 70vh; --rect-vert-min-h: 200px;
  --rect-horz-w: 28vw; --rect-horz-min-w: 280px; --rect-horz-h: 12vw; --rect-horz-min-h: 120px;
}

html, body { 
  height:100%; margin:0; padding:0; overflow:hidden; 
  font-family: var(--font-family); background-color: var(--c-bg);
  touch-action: none; overscroll-behavior: none;
  -webkit-user-select: none; user-select: none;
}
* { -webkit-tap-highlight-color: transparent; user-select:none; }
input[type=range] { touch-action: none; }

.container{
  display:flex; justify-content:space-between; align-items:center; gap: var(--col-gap);
  width:100%; max-width: var(--container-max-w); margin:0 auto; height:100vh; padding:2vh 2vw; box-sizing:border-box;
}
.column{ display:flex; flex-direction:column; align-items:center; justify-content:center; }

#info{ font-family: Consolas, monospace; font-size:1.5vw; text-align:center; padding:1vw; min-width:20vw; max-width:40vw; color: var(--c-text); pointer-events: none; }
p{ font-size:2.2vw; margin:0.5vw 0; pointer-events: none; }

.toggle{ display:flex; flex-direction:column; align-items:center; margin-bottom:1.5vw; z-index: 10; }
.toggle-label{ font-size:1.2vw; font-weight:700; color: var(--c-text); margin-bottom: 0.5vw; text-align: center; pointer-events: none; }

/* Switch Style */
.switch{
  --w: var(--sw-w); --h: var(--sw-h); --pad: var(--sw-pad);
  width: var(--w); height: var(--h); position:relative;
  max-width:120px; max-height:56px; min-width:70px; min-height:32px;
  cursor: pointer; 
}
.switch input{ display: none; } 
.switch .track{ position:absolute; inset:0; border-radius: calc(var(--h)); background: var(--c-switch-off); transition: background .22s; pointer-events: none;}
.switch .slider-round{ position:absolute; top:var(--pad); left:var(--pad); width:calc(var(--h)*0.8); height:calc(var(--h)*0.8); border-radius:50%; background:#fff; box-shadow:0 0.25vw 0.6vw rgba(0,0,0,.3); transition:left .22s; pointer-events: none;}
.switch.active .track{ background: var(--c-switch-on); }
.switch.active .slider-round{ left: calc(var(--w) - var(--pad) - (var(--h)*0.8)); }

.control-rect{
  background: var(--c-bg); border:2px solid var(--c-card-bd); border-radius: var(--radius-card);
  box-shadow: var(--shadow-card); position:relative; display:flex; align-items:center; justify-content:center; padding: var(--rect-pad);
}
.control-rect.vertical{ --rectHpx:150px; width: var(--rect-vert-w); min-width: var(--rect-vert-min-w); height: var(--rect-vert-h); min-height: var(--rect-vert-min-h);}
.slider-vertical-wrap{ position:relative; width:100%; height:100%; display:flex; align-items:center; justify-content:center; }
.control-rect.horizontal{ width: var(--rect-horz-w); min-width: var(--rect-horz-min-w); height: var(--rect-horz-h); min-height: var(--rect-horz-min-h); }

/* CSS GỐC CHO iOS - GIỮ NGUYÊN */
input[type=range].vertical{ -webkit-appearance:none; appearance:none; width: calc(var(--rectHpx) * 0.90) !important; height:40px; transform:rotate(-90deg); transform-origin:50% 50%; background:transparent; outline:none; }
@supports (-webkit-appearance: slider-vertical){
  input[type=range].vertical{ transform:none; -webkit-appearance: slider-vertical; writing-mode: bt-lr; width:40px !important; height: calc(var(--rectHpx) * 0.90) !important; }
}
input[type=range].vertical::-webkit-slider-runnable-track{ height: var(--slider-track-h); background: var(--c-track); border-radius:999px; }
input[type=range].vertical::-webkit-slider-thumb{ -webkit-appearance:none; width: var(--thumb-vert-w); height: var(--thumb-vert-h); border-radius:50%; background: var(--c-thumb-1); box-shadow: var(--shadow-thumb); margin-top:0; }
input[type=range].vertical::-moz-range-track{ height: var(--slider-track-h); background: var(--c-track); border-radius:999px; }
input[type=range].vertical::-moz-range-thumb{ width: var(--thumb-vert-w); height: var(--thumb-vert-h); border:none; border-radius:50%; background: var(--c-thumb-1); }

input[type=range].flat{ -webkit-appearance:none; appearance:none; width:90%; height:36px; background:transparent; outline:none; }
input[type=range].flat::-webkit-slider-runnable-track{ height: 80px; background: var(--c-track); border-radius:999px; }
input[type=range].flat::-webkit-slider-thumb{ -webkit-appearance:none; width: var(--thumb-horz-w); height: var(--thumb-horz-h); border-radius:50%; background: var(--c-thumb-2); box-shadow: var(--shadow-thumb); margin-top:0; }
input[type=range].flat::-moz-range-track{ height: 80px; background: var(--c-track); border-radius:999px; }
input[type=range].flat::-moz-range-thumb{ width: var(--thumb-horz-w); height: var(--thumb-horz-h); border:none; border-radius:50%; background: var(--c-thumb-2); }

.disabled { filter: grayscale(0.5) opacity(0.6); pointer-events: none; }

/* Vạch sóng WiFi */
.wifi-bars {
  display: inline-flex;
  gap: 2px;
  align-items: flex-end;
  margin-left: 4px;
}
.wifi-bars .bar {
  width: 4px;
  background-color: #aaa;
  border-radius: 1px;
  transition: background-color 0.1s;
}
.wifi-bars .bar:nth-child(1) { height: 3px; }
.wifi-bars .bar:nth-child(2) { height: 6px; }
.wifi-bars .bar:nth-child(3) { height: 9px; }
.wifi-bars .bar:nth-child(4) { height: 12px; }

@media (orientation:landscape){
  .switch{ --w:26vh; --h:11vh; --pad:1.1vh; }
  .toggle-label{ font-size:2.2vh; }
}
@media (orientation:portrait){
  .switch{ --w:14vh; --h:8vh; --pad:0.6vh; }
  .switch .slider-round{ width: calc(var(--h) * 0.86); height: calc(var(--h) * 0.86); top: calc(var(--pad) - 0.3vh); }
  .toggle-label{ font-size:1.8vh; }
}

/* ========== CSS RIÊNG CHO ANDROID ========== */
.android .control-rect.vertical {
  height: 78vh;
  min-height: 280px;
}
.android .slider-vertical-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: visible;
}

.android .control-rect.horizontal {
  width: 25vw;
  min-width: 250px;
  margin: 0 auto;
}
.android input[type=range].vertical {
  -webkit-appearance: none !important;
  appearance: none !important;
  width: calc(var(--rectHpx) - 40px) !important;
  height: 80px !important;
  background: transparent;
  position: absolute;
  transform: rotate(-90deg) !important;
  outline: none;
  margin: 0;
  padding: 0;
  cursor: pointer;
}
.android input[type=range].vertical::-webkit-slider-runnable-track {
  height: 80px;
  background: var(--c-track);
  border-radius: 40px;
  border: none;
}
.android input[type=range].vertical::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: var(--thumb-vert-w);
  height: var(--thumb-vert-h);
  background: var(--c-thumb-1);
  border-radius: 50%;
  box-shadow: var(--shadow-thumb);
  margin-top: 0px !important;
}
.android #info {
  font-size: 1.2vw;
  max-width: 45vw;
  line-height: 1.3;
}
.android .container {
  height: calc(var(--vh, 1vh) * 100);
}
@media (max-width: 700px) {
  .android #info { font-size: 2vw; }
}
@media (max-width: 500px) {
  .android #info { font-size: 2.8vw; }
}
</style>
</head>

<body>
<div class="container">
  <div class="column">
    <div class="control-rect vertical">
      <div class="slider-vertical-wrap">
        <input type="range" id="dcSlider" class="vertical" min="-0.70" max="0.70" value="0.00" step="0.01">
      </div>
    </div>
  </div>

  <div class="column">
    <p style="text-align:center;"><b>REMOTE</b></p>
    <div class="toggle">
      <div class="toggle-label">Autonomous</div>
      <div class="switch" id="swAuto">
        <input type="checkbox" id="autoToggle">
        <span class="track"></span>
        <span class="slider-round"></span>
      </div>
    </div>
    <div class="toggle">
      <div class="toggle-label">Cruise Control</div>
      <div class="switch" id="swCruise">
        <input type="checkbox" id="cruiseToggle">
        <span class="track"></span>
        <span class="slider-round"></span>
      </div>
    </div>
    <div id="info">Loading...</div>
  </div>

  <div class="column">
    <div class="control-rect horizontal">
      <input type="range" id="servoSlider" class="flat" min="-30" max="30" value="0" step="1">
    </div>
  </div>
</div>

<script>
// Phát hiện trình duyệt
(function() {
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
  if (isIOS || isSafari) {
    document.body.classList.add('ios');
  } else {
    document.body.classList.add('android');
    function setVh() {
      let vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty('--vh', `${vh}px`);
    }
    window.addEventListener('resize', setVh);
    setVh();
  }
})();

document.addEventListener('contextmenu', e => e.preventDefault());

const dcSlider = document.getElementById('dcSlider');
const servoSlider = document.getElementById('servoSlider');
const autoToggle = document.getElementById('autoToggle');
const cruiseToggle = document.getElementById('cruiseToggle');
const swAuto = document.getElementById('swAuto');
const swCruise = document.getElementById('swCruise');
const info = document.getElementById('info');


function syncDCSliderLength(){
  const rect = document.querySelector('.control-rect.vertical');
  if(rect) rect.style.setProperty('--rectHpx', rect.clientHeight + 'px');
}
addEventListener('load', syncDCSliderLength);
addEventListener('resize', syncDCSliderLength);

const WHEEL_DIAM_M = 0.075;
const RPM2MS = Math.PI * WHEEL_DIAM_M / 60.0;
const SERVO_CENTER = 88;
const STEER_PER_SERVO = 30.0 / 47.0; 
const DEAD_MPS = 0.02;
const HOLD_MPS = 0.00;

let ws;
// === Làm tròn dc đến 2 chữ số, sv thành số nguyên ===
function sendCombined(dc, sv) {
  if (ws && ws.readyState === 1) {
    ws.send(`dc:${dc.toFixed(2)};sv:${sv.toFixed(0)}`);
    lastOutboundTime = Date.now(); 
  }
}

// Lưu giá trị đã gửi cuối cùng
let lastSentDC = 0, lastSentSV = 0;
let fastSendInterval = null;
let lastChangeTime = 0;
let lastOutboundTime = Date.now(); 

function sendIfChanged() {
  // Ưu tiên lấy giá trị thực tế đang hiển thị trên thanh trượt
  let targetDC = dcDrag ? clampDC(+dcSlider.value) : clampDC(rampCmdDC);
  let targetSV = svDrag ? clampSV(+servoSlider.value) : clampSV(rampCmdSV);
  
  if (Math.abs(targetDC) < DEAD_MPS) targetDC = 0;
  
  // Kiểm tra thay đổi với ngưỡng nhạy hơn
  let dcChanged = Math.abs(targetDC - lastSentDC) > 0.005; 
  let svChanged = Math.abs(targetSV - lastSentSV) > 0.5;
  
  if (dcChanged || svChanged) {
    sendCombined(targetDC, targetSV);
    lastSentDC = targetDC;
    lastSentSV = targetSV;
    lastChangeTime = Date.now();
  }
}

// === VÒNG LẶP: 30ms, heartbeat chỉ khi cần, tự động dừng ===
function startFastSend() {
  if (fastSendInterval) return;
  fastSendInterval = setInterval(() => {
    const now = Date.now();
    
    // 1. Gửi lệnh lái nếu có thay đổi
    sendIfChanged();

    // 2. Heartbeat chỉ gửi nếu trong 250ms không có lệnh nào
    if (now - lastOutboundTime > 250) {
      if (ws && ws.readyState === 1) {
        ws.send('hb');
        lastOutboundTime = now;
      }
    }
  }, 30); // 30ms (~33 fps)
}

function setSwitchState(swEl, checkbox, checked) {
  checkbox.checked = checked;
  if(checked) swEl.classList.add('active');
  else swEl.classList.remove('active');
}

function forceSyncVisuals() {
    if(autoToggle.checked && !swAuto.classList.contains('active')) swAuto.classList.add('active');
    if(!autoToggle.checked && swAuto.classList.contains('active')) swAuto.classList.remove('active');
    if(cruiseToggle.checked && !swCruise.classList.contains('active')) swCruise.classList.add('active');
    if(!cruiseToggle.checked && swCruise.classList.contains('active')) swCruise.classList.remove('active');
}

function updateUiByMode(isAuto){
  const vertRect = document.querySelector('.control-rect.vertical');
  const horzRect = document.querySelector('.control-rect.horizontal');
  if(isAuto){
    dcSlider.disabled = true;
    servoSlider.disabled = true;
    setSwitchState(swCruise, cruiseToggle, false); 
    swCruise.style.pointerEvents = 'none'; 
    swCruise.style.opacity = '0.5';
    vertRect && vertRect.classList.add('disabled');
    horzRect && horzRect.classList.add('disabled');
  }else{
    dcSlider.disabled = false;
    servoSlider.disabled = false;
    swCruise.style.pointerEvents = 'auto'; 
    swCruise.style.opacity = '1.0';
    vertRect && vertRect.classList.remove('disabled');
    horzRect && horzRect.classList.remove('disabled');
  }
}

function wsConnect(){
  ws = new WebSocket(`ws://${location.hostname}:81/`);
  ws.onopen = () => { 
    syncDCSliderLength(); 
    startFastSend(); // Kích hoạt vòng lặp quản lý ngay khi kết nối
  };
  ws.onclose = ()=>setTimeout(wsConnect, 1000);
  ws.onerror = ()=>ws.close();
  ws.onmessage = (evt)=>{
    const s = evt.data;
    if (!s || typeof s !== 'string' || !s.startsWith('state:')) return;
    const kv = Object.fromEntries(s.slice(6).split(',').map(pair=>{
      const [k,v]=pair.split('='); return [k,v];
    }));
    const sv=parseFloat(kv.sv), rpm=parseFloat(kv.rpm), pwm=parseInt(kv.pwm), md=parseInt(kv.md||"0");
    
    if(!lastAutoInteraction) {
      const serverAuto = (md === 1);
      if(autoToggle.checked !== serverAuto) {
          setSwitchState(swAuto, autoToggle, serverAuto);
          updateUiByMode(serverAuto);
      }
    }
    forceSyncVisuals();
    
    const speedMs = isNaN(rpm) ? 0 : rpm * RPM2MS;
    const servoRel = (isNaN(sv)?0:(sv-SERVO_CENTER)); 
    const steerDeg = servoRel * STEER_PER_SERVO;

    let batVolt = '?V';
    if (kv.volt) {
      let voltNum = parseFloat(kv.volt);
      if (!isNaN(voltNum)) batVolt = voltNum.toFixed(2) + 'V';
    }
    let batPercent = (kv.bat !== undefined) ? kv.bat : '?';
    
    let wifiBarsHtml = '';
    if (kv.rssi !== undefined) {
        let rssi = parseInt(kv.rssi);
        let level = 0;
        if (rssi > -50) level = 4;
        else if (rssi > -60) level = 3;
        else if (rssi > -70) level = 2;
        else if (rssi > -80) level = 1;
        else level = 0;
        let bars = '';
        for (let i = 0; i < 4; i++) {
            let color = (i < level) ? '#22c55e' : '#aaa';
            bars += `<div class="bar" style="background:${color};"></div>`;
        }
        wifiBarsHtml = `<div class="wifi-bars">${bars}</div>`;
    } else {
        wifiBarsHtml = `<div class="wifi-bars"><div class="bar"></div><div class="bar"></div><div class="bar"></div><div class="bar"></div></div>`;
    }
    
    // Hàm nhỏ để chuyển đổi hiển thị -1 thành inf
    const fmtDist = (v) => (parseFloat(v) < 0 || isNaN(v)) ? "inf" : v + " cm";

    info.innerHTML = `Mode: <b>${md===1?'AUTONOMOUS':'MANUAL'}</b><br>` +
                    `WiFi: ${wifiBarsHtml}<br>` +
                    `🔋: ${batPercent}%<br>` +
                    `Setpoint: ${(+dcSlider.value).toFixed(2)} m/s<br>` +
                    `Speed: ${speedMs.toFixed(2)} m/s<br>` +
                    `DC PWM: ${isNaN(pwm)?0:pwm}<br>` +
                    `Steer: ${steerDeg.toFixed(2)}°<br>` +
                    `Pothole: ${fmtDist(kv.us1)}<br>` +
                    `Front: ${fmtDist(kv.us2)}<br>` +
                    `Rear: ${fmtDist(kv.us3)}`;
  };
}
wsConnect();

// === ĐÃ XÓA setInterval gửi hb cố định ===

// ====================== ĐIỀU KHIỂN RIÊNG DC & SV ======================
let dcDrag = false, svDrag = false;
let rampCmdDC = +dcSlider.value;
let rampCmdSV = +servoSlider.value;
let rampActiveDC = false, rampActiveSV = false;
let lastAutoInteraction = false;

function clampDC(x){ return Math.max(-0.70, Math.min(0.70, x)); }
function clampSV(x){ return Math.max(-30, Math.min(30, x)); }

function bindSliderPointer(slider, kind){
  slider.addEventListener('pointerdown', e=>{
    slider.setPointerCapture(e.pointerId);
    if(kind==='dc'){ dcDrag=true; rampActiveDC=false; rampCmdDC = clampDC(+dcSlider.value); }
    else           { svDrag=true; rampActiveSV=false; rampCmdSV = clampSV(+servoSlider.value); }
    sendIfChanged();
    startFastSend();
  });
  slider.addEventListener('pointermove', e=>{
    if(kind==='dc'){ rampCmdDC = clampDC(+dcSlider.value); }
    else           { rampCmdSV = clampSV(+servoSlider.value); }
    lastChangeTime = Date.now();
    sendIfChanged();
  });
  slider.addEventListener('pointerup', e=>{
    if(kind==='dc'){ 
        dcDrag=false; 
        if(cruiseToggle.checked) { rampActiveDC = false; rampCmdDC = clampDC(+dcSlider.value); }
        else { rampActiveDC=true; dcSlider.value = HOLD_MPS.toFixed(2); rampCmdDC = HOLD_MPS; }
    }
    else { 
        // Xử lý Servo khi buông tay
        svDrag = false; 
        rampActiveSV = false;
        rampCmdSV = 0;
        servoSlider.value = "0";
    }
    sendIfChanged();
  });
  slider.addEventListener('pointercancel', e=>{
     if(kind==='dc'){ 
        dcDrag=false; 
        if(cruiseToggle.checked) { rampActiveDC = false; rampCmdDC = clampDC(+dcSlider.value); }
        else { rampActiveDC=true; dcSlider.value = "0.00"; }
    } else { 
        svDrag = false; 
        rampActiveSV = false;
        rampCmdSV = 0;
        servoSlider.value = "0"; 
    }
    sendIfChanged();
  });
}
bindSliderPointer(dcSlider,'dc');
bindSliderPointer(servoSlider,'sv');

function bindFastSwitch(swEl, checkbox, onChange){
  swEl.addEventListener('pointerdown', (e) => {
    e.preventDefault(); e.stopPropagation(); 
    const newState = !checkbox.checked;
    setSwitchState(swEl, checkbox, newState);
    if(onChange) onChange(newState);
  });
  swEl.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); });
}

bindFastSwitch(swAuto, autoToggle, (state) => {
  lastAutoInteraction = true;
  updateUiByMode(state);
  rampActiveDC = false; rampActiveSV = false;
  rampCmdDC = 0; rampCmdSV = 0;
  dcSlider.value = "0.00"; servoSlider.value = "0";
  sendIfChanged();

  if (ws && ws.readyState === 1) {
    ws.send(`mode:${state ? 1 : 0}`);
  }
  
  setTimeout(() => lastAutoInteraction = false, 500);
});

bindFastSwitch(swCruise, cruiseToggle, (state) => {
  if(state) { rampActiveDC = false; rampCmdDC = clampDC(+dcSlider.value); }
  else { if(!dcDrag) { rampActiveDC = true; dcSlider.value = HOLD_MPS.toFixed(2); rampCmdDC = HOLD_MPS; } }
  sendIfChanged();
});

// Ramp về 0 khi thả tay
setInterval(() => {
  if (autoToggle.checked) return;
  let changed = false;

  // --- Logic DC ---
  if (rampActiveDC && !dcDrag && !cruiseToggle.checked) {
    rampCmdDC = Math.abs(rampCmdDC - HOLD_MPS) < 0.01 ? HOLD_MPS : rampCmdDC + (rampCmdDC > HOLD_MPS ? -0.04 : 0.04);
    dcSlider.value = rampCmdDC.toFixed(2);
    changed = true;
  }

  // --- Logic SERVO ---
  let targetSV = svDrag ? clampSV(+servoSlider.value) : 0;
  if (rampCmdSV !== targetSV) {
    rampCmdSV = targetSV;
    if (!svDrag) servoSlider.value = "0"; // Ép thanh trượt về 0 khi buông tay
    changed = true;
  }

  if (changed) {
    lastChangeTime = Date.now();
    sendIfChanged();
    if (!fastSendInterval) startFastSend();
  }
}, 50);
</script>
</body>
</html>
)rawliteral";