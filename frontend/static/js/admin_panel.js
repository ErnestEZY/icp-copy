function panel(){
  return {
    q:'', status:'', tag:'', items:[], detail:null, tagsInput:'',
    page: 1, perPage: 5,
    get totalPages(){ return Math.ceil(this.items.length / this.perPage) || 1 },
    get paginatedItems(){
      const start = (this.page - 1) * this.perPage;
      return this.items.slice(start, start + this.perPage);
    },
    nextPage(){ if(this.page < this.totalPages) { this.page++; this.renderList(); } },
    prevPage(){ if(this.page > 1) { this.page--; this.renderList(); } },
    goToPage(p){
      const n = parseInt(p);
      if(n > 0 && n <= this.totalPages) { this.page = n; this.renderList(); }
      else { this.renderList(); } // Reset input
    },
    escapeHtml(s){ return String(s).replace(/[&<>"']/g, m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[m])) },
    renderList(){
      const tbody = document.getElementById('list-body');
      if(!tbody) return;
      const rows = (this.paginatedItems||[]).map(it=>{
        const name = this.escapeHtml(it.filename || it.name || '(missing)');
        const status = this.escapeHtml(it.status || 'pending');
        const created = it.created_at ? new Date(it.created_at).toLocaleString('en-MY', { timeZone: 'Asia/Kuala_Lumpur' }) : '';
        const tags = Array.isArray(it.tags) && it.tags.length
          ? it.tags.map(t=>`<span class="badge bg-primary me-1">${this.escapeHtml(t)}</span>`).join('')
          : '<span class="text-secondary">—</span>';
        const statusClass = (it.status||'pending')==='approved' ? 'bg-success' : (it.status==='rejected' ? 'bg-danger' : 'bg-warning');
        const nameHtml = it.file_available ? `<a href="/static/pages/admin_file_preview.html?id=${this.escapeHtml(it.id)}" class="text-warning">${name}</a>` : name;
        const noteVal = this.escapeHtml(it.notes || '');
        const viewBtn = ( (it.status||'pending')==='approved' && it.file_available )
          ? `<button class="btn btn-outline-warning btn-sm ms-1 view-btn" data-id="${this.escapeHtml(it.id)}">View</button>`
          : '';
        return `
          <tr>
            <td>${nameHtml}</td>
            <td><span class="badge ${statusClass}">${status}</span></td>
            <td>${tags}</td>
            <td>${created}</td>
            <td style="min-width:320px">
              <textarea rows="5" class="form-control" placeholder="Notes" readonly>${noteVal}</textarea>
            </td>
            <td>
              <button class="btn btn-outline-light btn-sm detail-btn" data-id="${this.escapeHtml(it.id)}">Details</button>
              ${viewBtn}
            </td>
          </tr>`;
      }).join('');
      tbody.innerHTML = rows;
      tbody.querySelectorAll('.detail-btn').forEach(btn=>{
        btn.addEventListener('click', ()=> this.open(btn.getAttribute('data-id')));
      });
      tbody.querySelectorAll('.view-btn').forEach(btn=>{
        btn.addEventListener('click', ()=>{
          const id = btn.getAttribute('data-id');
          const url = '/static/pages/admin_file_preview.html?id='+encodeURIComponent(id);
          const w = window.open(url, '_blank');
          if(!w){ Swal.fire({icon:'error', title:'Popup blocked', text:'Please allow popups to view files'}); }
        });
      });
    },
    async init(){
      if(!icp.state.token){ window.location='/static/pages/admin.html'; return; }
      try{
        const me = await fetch('/api/auth/me',{headers:{'Authorization':'Bearer '+icp.state.token}}).then(r=>r.json());
        if(!(me.role==='admin'||me.role==='super_admin')){ window.location='/static/pages/admin.html'; return; }
      }catch(e){
        window.location='/static/pages/admin.html'; return;
      }
      this.load();
    },
    load(){
      const u = new URL('/api/admin/resumes', window.location.origin);
      if(this.q) u.searchParams.set('q', this.q);
      if(this.status) u.searchParams.set('status', this.status);
      if(this.tag) u.searchParams.set('tag', this.tag);
      fetch(u, {headers:{'Authorization':'Bearer '+icp.state.token}})
        .then(r=>{
          if(r.status===401){ window.location.href='/static/pages/login.html'; return []; }
          if(r.status===403){ Swal.fire({icon:'error', title:'Forbidden', text:'Admin privileges required'}); return []; }
          return r.json();
        })
        .then(j=>{
          const arr = Array.isArray(j) ? j : [];
          this.items = arr.map(it=>({
            id: it.id,
            filename: it.filename || it.name || '',
            status: it.status || 'pending',
            tags: Array.isArray(it.tags) ? it.tags : [],
            created_at: it.created_at || null,
            file_available: !!it.file_available,
            notes: it.notes || ''
          }));
          this.page = 1;
          this.renderList();
        });
    },
    open(id){
      fetch('/api/admin/resumes/'+id, {headers:{'Authorization':'Bearer '+icp.state.token}})
        .then(r=>{
          if(r.status===401){ window.location.href='/static/pages/login.html'; return null; }
          if(r.status===403){ Swal.fire({icon:'error', title:'Forbidden', text:'Admin privileges required'}); return null; }
          return r.json();
        })
        .then(j=>{
          if(!j) return;
          this.detail = {
            id: j.id,
            filename: j.filename || '',
            status: j.status || 'pending',
            text: j.text || '',
            notes: j.notes || '',
            tags: Array.isArray(j.tags) ? j.tags : [],
            created_at: j.created_at || null,
            file_available: !!j.file_available,
            mime_type: j.mime_type || ''
          };
          this.tagsInput = (this.detail.tags||[]).join(',');
        });
    },
    save(){
      const tags = this.tagsInput.split(',').map(s=>s.trim()).filter(Boolean);
      const params = new URLSearchParams();
      params.set('status', this.detail.status || 'pending');
      params.set('notes', this.detail.notes || '');
      params.set('tags', JSON.stringify(tags));
      const btns = document.querySelectorAll('.admin-status-select, .quick-save-btn');
      btns.forEach(b=>b.disabled=true);
      fetch('/api/admin/resumes/'+this.detail.id, {
          method:'PATCH',
          headers:{'Authorization':'Bearer '+icp.state.token, 'Content-Type':'application/x-www-form-urlencoded'},
          body: params.toString()
        })
        .then(async r=>{
          if(r.status===401){ window.location.href='/static/pages/login.html'; return; }
          if(!r.ok){
            let msg = 'Save failed';
            try{ const j = await r.json(); msg = j.detail || msg; }catch(e){}
            Swal.fire({icon:'error', title:'Error', text: msg});
            return;
          }
          Swal.fire({icon:'success', title:'Saved', timer:1000, showConfirmButton:false});
          // Refresh detail to reflect updated fields
          return fetch('/api/admin/resumes/'+this.detail.id, {headers:{'Authorization':'Bearer '+icp.state.token}})
            .then(rr=>rr.json())
            .then(j=>{
              this.detail.status = j.status || this.detail.status;
              this.detail.notes = j.notes || this.detail.notes;
              this.detail.tags = Array.isArray(j.tags) ? j.tags : this.detail.tags;
              this.tagsInput = (this.detail.tags||[]).join(',');
              this.load();
            });
        })
        .finally(()=>{ btns.forEach(b=>b.disabled=false); });
    }
  }
}
