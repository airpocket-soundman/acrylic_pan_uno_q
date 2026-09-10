const cameraFrame = document.getElementById('cameraFrame');
const cameraServerUrl = document.getElementById('cameraServerUrl');
const cameraServerApply = document.getElementById('cameraServerApply');
const defaultCameraServer = 'http://192.168.50.177:8878/';

function applyCameraServer() {
  const url = new URL(cameraServerUrl.value.trim() || defaultCameraServer);
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('HTTPまたはHTTPSのURLを指定してください。');
  cameraServerUrl.value = url.href;
  localStorage.setItem('acrylicPanPcCameraServer', url.href);
  cameraFrame.src = url.href;
}

cameraServerUrl.value = localStorage.getItem('acrylicPanPcCameraServer') || defaultCameraServer;
cameraServerApply.addEventListener('click', () => {
  try { applyCameraServer(); document.getElementById('error').textContent = ''; }
  catch (error) { document.getElementById('error').textContent = `PCカメラ配信: ${error.message}`; }
});
applyCameraServer();
