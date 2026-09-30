(() => {
  const setNetwork = () => document.body.classList.toggle('offline', !navigator.onLine);
  window.addEventListener('online', setNetwork); window.addEventListener('offline', setNetwork); setNetwork();
  document.querySelectorAll('[data-count]').forEach(el => { const target = Number(el.dataset.count); let n = 0; const step = Math.max(1, Math.ceil(target / 35)); const timer = setInterval(() => { n = Math.min(target, n + step); el.textContent = n.toLocaleString(); if (n >= target) clearInterval(timer); }, 28); });
  const video = document.querySelector('[data-consultation-video]');
  if (video && navigator.mediaDevices) { navigator.mediaDevices.getUserMedia({video:true,audio:true}).then(stream => { video.srcObject = stream; window.localStream = stream; document.querySelector('#connectionLabel')?.replaceChildren(document.createTextNode('Connected to device')); }).catch(() => { document.querySelector('#connectionLabel')?.replaceChildren(document.createTextNode('Camera/microphone permission not granted')); }); }
  document.querySelectorAll('[data-toggle-track]').forEach(btn => btn.addEventListener('click', () => { const kind = btn.dataset.toggleTrack; window.localStream?.getTracks().filter(t => t.kind === kind).forEach(t => t.enabled = !t.enabled); btn.classList.toggle('active'); }));
  document.querySelector('[data-end-call]')?.addEventListener('click', () => window.localStream?.getTracks().forEach(t => t.stop()));
  document.querySelector('[data-save-notes]')?.addEventListener('click', async e => { const btn=e.currentTarget; const id=btn.dataset.appointment; const notes=document.querySelector('#consultationNotes').value; const res=await fetch(`/api/consultations/${id}/notes`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({notes})}); btn.textContent=res.ok?'Saved':'Retry save'; setTimeout(()=>btn.textContent='Save notes',1300); });
})();
