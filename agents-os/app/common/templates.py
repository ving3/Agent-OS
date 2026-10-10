# -*- coding: utf-8 -*-
"""
Agentic OS — Pages HTML partagees (connexion, inscription)
"""

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agentic OS — Connexion</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:#0d1117; color:#c9d1d9; min-height:100vh;
  display:flex; align-items:center; justify-content:center; }
.auth-card { background:#161b22; border:1px solid #30363d; border-radius:12px;
  padding:40px; width:400px; max-width:90vw; }
.auth-card h1 { font-size:22px; color:#58a6ff; margin-bottom:8px; text-align:center; }
.auth-card .sub { color:#8b949e; font-size:13px; margin-bottom:24px; text-align:center; }
.form-group { margin-bottom:16px; }
.form-group label { display:block; font-size:12px; color:#8b949e; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px; }
.form-group input { width:100%; background:#0d1117; border:1px solid #30363d; border-radius:6px;
  padding:10px 12px; color:#c9d1d9; font-size:14px; outline:none; font-family:inherit; }
.form-group input:focus { border-color:#58a6ff; }
.btn { width:100%; padding:10px; border-radius:6px; border:none; font-size:14px;
  font-weight:600; cursor:pointer; font-family:inherit; }
.btn-primary { background:#238636; color:#fff; }
.btn-primary:hover { background:#2ea043; }
.btn:disabled { background:#30363d; color:#484f58; cursor:not-allowed; }
.error { background:#da363322; border:1px solid #da3633; border-radius:6px;
  padding:10px; color:#f85149; font-size:13px; margin-bottom:16px; display:none; }
.footer { text-align:center; margin-top:20px; font-size:13px; color:#8b949e; }
.footer a { color:#58a6ff; text-decoration:none; }
.footer a:hover { text-decoration:underline; }
.loader { display:inline-block; width:16px; height:16px; border:2px solid #484f58;
  border-top-color:#58a6ff; border-radius:50%; animation:spin 0.6s linear; vertical-align:middle; }
@keyframes spin { to { transform:rotate(360deg); } }
</style></head>
<body>
<div class="auth-card">
  <h1>⚡ Agentic OS</h1>
  <div class="sub">Connectez-vous pour acceder au tableau de bord</div>
  <div class="error" id="error"></div>
  <form id="loginForm" onsubmit="return doLogin(event)">
    <div class="form-group">
      <label>Email</label>
      <input type="email" id="email" placeholder="ex: admin@local.home" required autofocus>
    </div>
    <div class="form-group">
      <label>Mot de passe</label>
      <input type="password" id="password" placeholder="Votre mot de passe" required>
    </div>
    <button type="submit" class="btn btn-primary" id="submitBtn">Se connecter</button>
  </form>
  <div class="footer">Pas encore de compte ? <a href="/signup">Creer un compte</a></div>
</div>
<script>
async function doLogin(e) {
  e.preventDefault(); const btn=document.getElementById('submitBtn'); const err=document.getElementById('error');
  btn.disabled=true; btn.innerHTML='<span class="loader"></span>'; err.style.display='none';
  try {
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:document.getElementById('email').value,password:document.getElementById('password').value})});
    const d=await r.json();
    if(d.error) { err.textContent=d.error; err.style.display='block'; btn.disabled=false; btn.textContent='Se connecter'; return; }
    document.cookie='token='+d.token+'; Path=/; SameSite=Lax';
    window.location.href='/dashboard';
  } catch(e) { err.textContent='Erreur de connexion'; err.style.display='block'; btn.disabled=false; btn.textContent='Se connecter'; }
  return false;
}
</script>
</body></html>"""

SIGNUP_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agentic OS — Inscription</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:#0d1117; color:#c9d1d9; min-height:100vh;
  display:flex; align-items:center; justify-content:center; }
.auth-card { background:#161b22; border:1px solid #30363d; border-radius:12px;
  padding:40px; width:400px; max-width:90vw; }
.auth-card h1 { font-size:22px; color:#58a6ff; margin-bottom:8px; text-align:center; }
.auth-card .sub { color:#8b949e; font-size:13px; margin-bottom:24px; text-align:center; }
.form-group { margin-bottom:16px; }
.form-group label { display:block; font-size:12px; color:#8b949e; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px; }
.form-group input { width:100%; background:#0d1117; border:1px solid #30363d; border-radius:6px;
  padding:10px 12px; color:#c9d1d9; font-size:14px; outline:none; font-family:inherit; }
.form-group input:focus { border-color:#58a6ff; }
.btn { width:100%; padding:10px; border-radius:6px; border:none; font-size:14px;
  font-weight:600; cursor:pointer; font-family:inherit; }
.btn-primary { background:#238636; color:#fff; }
.btn-primary:hover { background:#2ea043; }
.error { background:#da363322; border:1px solid #da3633; border-radius:6px;
  padding:10px; color:#f85149; font-size:13px; margin-bottom:16px; display:none; }
.footer { text-align:center; margin-top:20px; font-size:13px; color:#8b949e; }
.footer a { color:#58a6ff; text-decoration:none; }
.footer a:hover { text-decoration:underline; }
.info { background:#1f6feb22; border:1px solid #1f6feb; border-radius:6px;
  padding:10px; color:#58a6ff; font-size:12px; margin-bottom:16px; }
</style></head>
<body>
<div class="auth-card">
  <h1>⚡ Agentic OS</h1>
  <div class="sub" id="subtitle">Creez votre compte</div>
  <div class="error" id="error"></div>
  <div class="info" id="firstUserInfo">Premier compte = administrateur</div>
  <form id="signupForm" onsubmit="return doSignup(event)">
    <div class="form-group">
      <label>Nom</label>
      <input type="text" id="name" placeholder="Votre nom" required autofocus>
    </div>
    <div class="form-group">
      <label>Email</label>
      <input type="email" id="email" placeholder="ex: user@local.home" required>
    </div>
    <div class="form-group">
      <label>Mot de passe</label>
      <input type="password" id="password" placeholder="Minimum 6 caracteres" required minlength="6">
    </div>
    <button type="submit" class="btn btn-primary" id="submitBtn">Creer mon compte</button>
  </form>
  <div class="footer">Deja un compte ? <a href="/login">Se connecter</a></div>
</div>
<script>
async function doSignup(e) {
  e.preventDefault(); const btn=document.getElementById('submitBtn'); const err=document.getElementById('error');
  btn.disabled=true; btn.innerHTML='<span class="loader"></span>'; err.style.display='none';
  try {
    const r=await fetch('/api/signup',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:document.getElementById('name').value,email:document.getElementById('email').value,password:document.getElementById('password').value})});
    const d=await r.json();
    if(d.error) { err.textContent=d.error; err.style.display='block'; btn.disabled=false; btn.textContent='Creer mon compte'; return; }
    document.cookie='token='+d.token+'; Path=/; SameSite=Lax';
    window.location.href='/dashboard';
  } catch(e) { err.textContent='Erreur'; err.style.display='block'; btn.disabled=false; btn.textContent='Creer mon compte'; }
  return false;
}
</script>
</body></html>"""
