const trainingStart=document.getElementById('trainingStart'),trainingStatus=document.getElementById('trainingStatus');
async function trainingApi(path,options={}){const response=await fetch(path,{...options,headers:{'Content-Type':'application/json'}}),data=await response.json();if(!response.ok)throw new Error(data.error||response.statusText);return data;}
async function refreshTraining(){if(!trainingStatus)return;try{const data=await trainingApi('/api/training/status');trainingStart.disabled=Boolean(data.active);trainingStatus.textContent=data.active?'再学習中…':data.last_error?`失敗: ${data.last_error}`:data.last_report?`完了（実測 ${data.last_report.fresh_mpu9250_event_count}件）`:'待機中';}catch(error){trainingStatus.textContent=error.message;}}
if(trainingStart)trainingStart.onclick=async()=>{try{await trainingApi('/api/training/start',{method:'POST',body:'{}'});await refreshTraining();}catch(error){trainingStatus.textContent=error.message;}};
refreshTraining();setInterval(refreshTraining,1000);
