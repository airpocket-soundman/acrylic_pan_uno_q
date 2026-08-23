const board=document.querySelector('#board'),marker=document.querySelector('#marker'),expectedMarker=document.querySelector('#expectedMarker');
const canvas=document.querySelector('#heatmap'),ctx=canvas.getContext('2d');
const zones=Array.from({length:12},(_,i)=>{const z=document.createElement('div');z.className='zone';z.style.left=`${i%4*25}%`;z.style.top=`${Math.floor(i/4)*33.333}%`;z.textContent=`AREA ${i+1}`;board.append(z);return z;});
Array.from({length:12},(_,i)=>{const b=document.createElement('button');b.textContent=`A${i+1}`;b.onclick=()=>fetch(`/api/demo/${i}`,{method:'POST'});document.querySelector('#cases').append(b);});

function heatColor(value){
  const t=Math.max(0,Math.min(1,value));
  const stops=[[0,3,7,30],[.14,20,30,140],[.30,0,105,255],[.46,0,220,235],[.62,45,210,80],[.76,245,235,30],[.89,255,120,10],[1,220,15,5]];
  for(let i=1;i<stops.length;i++){
    if(t<=stops[i][0]){
      const a=stops[i-1],b=stops[i],mix=(t-a[0])/(b[0]-a[0]);
      return a.slice(1).map((v,j)=>Math.round(v+(b[j+1]-v)*mix));
    }
  }
  return stops.at(-1).slice(1);
}

function drawHeat(result){
  const points=result.support_xy_mm||[],prob=result.position_probabilities||[];
  const rasterWidth=40,rasterHeight=30,sigmaMm=27,inv=1/(2*sigmaMm*sigmaMm);
  const density=new Float32Array(rasterWidth*rasterHeight);
  let peak=1e-12;
  for(let row=0;row<rasterHeight;row++){
    const y=(row+.5)*300/rasterHeight;
    for(let col=0;col<rasterWidth;col++){
      const x=(col+.5)*400/rasterWidth;
      let value=0;
      points.forEach(([sx,sy],i)=>{const dx=x-sx,dy=y-sy;value+=(prob[i]||0)*Math.exp(-(dx*dx+dy*dy)*inv);});
      density[row*rasterWidth+col]=value;
      peak=Math.max(peak,value);
    }
  }
  const raster=document.createElement('canvas');raster.width=rasterWidth;raster.height=rasterHeight;
  const rasterCtx=raster.getContext('2d'),image=rasterCtx.createImageData(rasterWidth,rasterHeight);
  density.forEach((value,i)=>{const normalized=Math.pow(value/peak,.52),quantized=Math.round(normalized*9)/9,[r,g,b]=heatColor(quantized),p=i*4;image.data[p]=r;image.data[p+1]=g;image.data[p+2]=b;image.data[p+3]=255;});
  rasterCtx.putImageData(image,0,0);
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.imageSmoothingEnabled=false;
  ctx.drawImage(raster,0,0,canvas.width,canvas.height);
}
function show(data){if(!data)return;drawHeat(data);marker.style.left=`${data.map_x_mm/4}%`;marker.style.top=`${data.map_y_mm/3}%`;expectedMarker.style.left=`${data.expected_x_mm/4}%`;expectedMarker.style.top=`${data.expected_y_mm/3}%`;zones.forEach((z,i)=>z.classList.toggle('active',i===data.predicted_class));document.querySelector('#map').textContent=`${data.map_x_mm.toFixed(0)}, ${data.map_y_mm.toFixed(0)}`;document.querySelector('#expected').textContent=`${data.expected_x_mm.toFixed(1)}, ${data.expected_y_mm.toFixed(1)}`;document.querySelector('#zone').textContent=`AREA ${data.predicted_class+1}`;document.querySelector('#confidence').textContent=`${(data.peak_probability*100).toFixed(1)}%`;document.querySelector('#credible').textContent=`${data.credible_90_indices.length} cells`;document.querySelector('#latency').textContent=data.inference_us<1000?`${data.inference_us} µs`:`${(data.inference_us/1000).toFixed(1)} ms`;}
async function poll(){try{const s=await fetch('/api/status').then(r=>r.json());document.querySelector('#runtime').textContent=`UNO Q 稼働中 · ${s.event_count} events`;document.querySelector('#sensor').textContent=s.sensor_ready?'KX134 接続済み':'KX134 未接続 · 保存波形デモ';document.querySelector('#sensor').className=`pill ${s.sensor_ready?'live':'warn'}`;show(s.latest);}catch(e){document.querySelector('#runtime').textContent='UNO Q 応答なし';}}
fetch('/api/self-test').then(r=>r.json()).then(({cases})=>{document.querySelector('#selftest').innerHTML=cases.map(c=>`<tr><td>A${c.case_id+1}　教師 (${c.target_x_mm.toFixed(0)}, ${c.target_y_mm.toFixed(0)}) mm</td><td>移植差 ${c.portable_delta_mm.toFixed(6)} mm · ${(c.inference_us/1000).toFixed(1)} ms</td></tr>`).join('');});
poll();setInterval(poll,350);
