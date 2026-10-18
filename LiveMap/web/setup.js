'use strict';
const form=document.getElementById('import-form'),button=document.getElementById('import'),file=document.getElementById('disc'),status=document.getElementById('status'),error=document.getElementById('error'),progress=document.getElementById('progress');
let token=null,busy=false;
async function refresh(){
  try{
    const response=await fetch('/api/setup');if(!response.ok)throw Error('Cannot contact the local minimap.');
    const state=await response.json();token=state.token;
    if(state.ready){location.reload();return;}
    if(state.busy){status.textContent=state.message;button.disabled=true;file.disabled=true;}
    else if(!busy){button.disabled=false;file.disabled=false;}
  }catch(e){status.textContent='Local minimap connection lost. Keep its launcher window open.';}
}
form.addEventListener('submit',async event=>{
  event.preventDefault();if(busy||!file.files.length)return;
  const image=file.files[0];error.hidden=true;
  if(!/\.(bin|iso)$/i.test(image.name)||image.size>1024*1024*1024||image.size<32769){error.textContent='Choose a data-track BIN or ISO up to 1 GiB.';error.hidden=false;return;}
  if(!token){await refresh();if(!token)return;}
  busy=true;button.disabled=true;file.disabled=true;progress.hidden=false;progress.value=0;status.textContent='Reading your disc locally…';
  const request=new XMLHttpRequest();request.open('POST','/api/import');request.setRequestHeader('Content-Type','application/octet-stream');request.setRequestHeader('X-Setup-Token',token);
  request.upload.onprogress=e=>{if(e.lengthComputable){progress.value=100*e.loaded/e.total;status.textContent=e.loaded===e.total?'Building your textured maps…':'Transferring locally: '+Math.round(progress.value)+'%';}};
  const finish=message=>{busy=false;button.disabled=false;file.disabled=false;progress.hidden=true;if(message){error.textContent=message;error.hidden=false;}};
  request.onerror=()=>finish('Connection lost. Keep the minimap launcher open, then try again.');
  request.onload=()=>{let result;try{result=JSON.parse(request.responseText);}catch{finish('Import failed. Check the minimap launcher, then try again.');return;}if(request.status===200&&result.ready){location.reload();return;}finish(result.error||'Could not import this image.');};
  request.send(image);
});
refresh();setInterval(refresh,1000);
