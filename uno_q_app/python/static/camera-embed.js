const cameraFrame = document.getElementById('cameraFrame');
const cameraServerUrl = document.getElementById('cameraServerUrl');
const cameraServerApply = document.getElementById('cameraServerApply');
const defaultCameraServer = `${window.location.protocol}//${window.location.hostname}:4912/embed`;

function applyCameraServer() {
  const url = new URL(cameraServerUrl.value.trim() || defaultCameraServer);
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('HTTPまたはHTTPSのURLを指定してください。');
  cameraServerUrl.value = url.href;
  localStorage.setItem('acrylicPanUnoQCameraServer', url.href);
  cameraFrame.src = url.href;
}

cameraServerUrl.value = localStorage.getItem('acrylicPanUnoQCameraServer') || defaultCameraServer;
cameraServerApply.addEventListener('click', () => {
  try { applyCameraServer(); document.getElementById('error').textContent = ''; }
  catch (error) { document.getElementById('error').textContent = `UNO Qカメラ配信: ${error.message}`; }
});
applyCameraServer();
