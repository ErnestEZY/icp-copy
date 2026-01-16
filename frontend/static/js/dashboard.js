function dashboard() {
  return {
    logged: !!icp.state.token,
    isAdmin: false,
    hasAnalyzed: false,
    sessionTime: 0,
    timerId: null,
    isLoading: true,
    feedback: null,
    uploading: false,
    hasHistory: false,
    fileName: '',
    targetJobTitle: localStorage.getItem('target_job_title') || '',
    resumeAttempts: 0,
    maxResumeAttempts: 5,
    persistedFileName: '',

    formatTime(seconds) {
      if (isNaN(seconds) || seconds === null || seconds === undefined) return '0:00';
      const totalSeconds = Math.max(0, Math.floor(seconds));
      const m = Math.floor(totalSeconds / 60);
      const s = totalSeconds % 60;
      return `${m}:${s.toString().padStart(2, '0')}`;
    },

    checkAdmin() {
      if (!this.logged) return;
      fetch('/api/auth/me', {
        headers: { 'Authorization': 'Bearer ' + icp.state.token }
      })
      .then(r => r.json())
      .then(me => {
        this.isAdmin = me.role === 'admin' || me.role === 'super_admin';
        const localFeedback = localStorage.getItem('resume_feedback');
        const hasLocal = localFeedback && localFeedback !== 'null' && localFeedback !== 'undefined';
        this.hasAnalyzed = me.has_analyzed || hasLocal;
      })
      .catch(() => { this.isAdmin = false; });
    },

    startTimer() {
      if (this.timerId) return;
      const token = icp.state.token;
      if (!token) return;
      const payload = icp.decodeToken(token);
      if (!payload || !payload.exp) return;
      const exp = payload.exp;
      localStorage.setItem('session_expiry_user', exp);
      const now = Math.floor(Date.now() / 1000);
      this.sessionTime = Math.max(0, exp - now);
      this.timerId = setInterval(() => {
        if (this.sessionTime > 0) {
          this.sessionTime--;
        } else {
          clearInterval(this.timerId);
          this.timerId = null;
          localStorage.removeItem('session_expiry_user');
          alert('Your session has expired. Please login again.');
          icp.logout();
        }
      }, 1000);
    },

    async initDashboard() {
      try {
        const stored = localStorage.getItem('resume_feedback');
        if (stored && stored !== 'null' && stored !== 'undefined') {
          this.feedback = JSON.parse(stored);
          this.hasAnalyzed = true;
        }
        this.persistedFileName = localStorage.getItem('resume_filename') || '';
        
        // Fallback: If hasAnalyzed is true but no local feedback, fetch from backend
        if (!this.feedback && this.logged) {
          fetch('/api/resume/my', {
            headers: { 'Authorization': 'Bearer ' + icp.state.token }
          })
          .then(r => r.ok ? r.json() : [])
          .then(items => {
            if (items && items.length > 0) {
              const latest = items.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
              if (latest && latest.feedback) {
                this.feedback = latest.feedback;
                this.hasAnalyzed = true;
                
                // Do NOT automatically sync job title/location from backend here
                // to ensure the fields remain clean as requested by the user.
                
                localStorage.setItem('resume_feedback', JSON.stringify(latest.feedback));
                localStorage.setItem('resume_filename', latest.filename || '');
                this.persistedFileName = latest.filename || '';
              }
            }
          })
          .catch(e => {});
        }
      } catch (e) {}

      const timeoutId = setTimeout(() => {
        if (this.isLoading) {
          this.isLoading = false;
        }
      }, 5000);

      try {
        await Promise.allSettled([
          (async () => {
            try {
              const r = await fetch('/api/interview/history', { headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') } });
              if (r.status === 200) {
                const j = await r.json();
                this.hasHistory = Array.isArray(j) && j.length > 0;
              }
            } catch (e) {}
          })(),
          (async () => {
            try {
              const r = await fetch('/api/resume/limits', { headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') } });
              if (r.status === 200) {
                const j = await r.json();
                this.resumeAttempts = j.remaining;
                this.maxResumeAttempts = j.limit;
              }
            } catch (e) {}
          })()
        ]);
      } finally {
        clearTimeout(timeoutId);
        setTimeout(() => { this.isLoading = false; }, 500);
      }
    },

    async uploadResume() {
      const jt = document.getElementById('jobTitle').value.trim();
      if (!jt) {
        Swal.fire('Error', 'Please enter a target job title', 'error');
        return;
      }
      const fileInput = document.getElementById('resumeFile');
      if (!fileInput.files[0]) {
        Swal.fire('Error', 'Please select a resume file', 'error');
        return;
      }

      Swal.fire({
        title: 'Analyzing Resume...',
        text: 'Please wait while our AI evaluates your profile for the ' + jt + ' position.',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading() }
      });

      const fd = new FormData();
      fd.append('file', fileInput.files[0]);
      fd.append('job_title', jt);
      fd.append('consent', document.getElementById('consent').checked);

      try {
        const r = await fetch('/api/resume/upload', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + icp.state.token },
          body: fd
        });
        const res = await r.json();
        if (r.ok) {
          Swal.close();
          this.persistedFileName = fileInput.files[0].name;
          localStorage.setItem('resume_filename', this.persistedFileName);
          this.fileName = '';
          fileInput.value = '';

          if (res && res.feedback) {
            this.feedback = res.feedback;
            this.hasAnalyzed = true;
            localStorage.setItem('resume_feedback', JSON.stringify(res.feedback));

            // Prioritize AI-detected/refined job title
            const finalTitle = res.job_title || jt;
            this.targetJobTitle = finalTitle;
            localStorage.setItem('target_job_title', finalTitle);

            if (res.feedback.Location) {
              localStorage.setItem('target_location', res.feedback.Location);
            }
            this.resumeAttempts = Math.max(0, this.resumeAttempts - 1);

            Swal.fire({
              icon: 'success',
              title: 'Analysis Complete',
              text: 'Your profile has been successfully analyzed!',
              timer: 2000,
              showConfirmButton: false
            });
          } else {
            throw new Error('Invalid response from server');
          }
        } else {
          throw new Error(res.detail || 'Upload failed');
        }
      } catch (err) {
        Swal.close();
        Swal.fire('Error', err.message || 'Failed to analyze resume', 'error');
        console.error('Upload error:', err);
      }
    },

    exportToPDF() {
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF();
      doc.setFontSize(22);
      doc.setTextColor(37, 99, 235);
      doc.text('Resume Analysis Report', 20, 20);
      doc.setFontSize(10);
      doc.setTextColor(100, 116, 139);
      const date = new Date().toLocaleDateString('en-MY', { timeZone: 'Asia/Kuala_Lumpur' });
      const job = localStorage.getItem('target_job_title') || 'Not specified';
      doc.text(`Date: ${date}`, 20, 30);
      doc.text(`Target Role: ${job}`, 20, 35);
      doc.text(`Score: ${this.feedback.Score}/100`, 20, 40);
      let yPos = 55;
      const drawSection = (title, items, color) => {
        doc.setFontSize(14);
        doc.setTextColor(color[0], color[1], color[2]);
        doc.text(title, 20, yPos);
        yPos += 8;
        doc.setFontSize(11);
        doc.setTextColor(51, 65, 85);
        items.forEach(item => {
          const lines = doc.splitTextToSize(`• ${item}`, 170);
          if (yPos + (lines.length * 7) > 280) {
            doc.addPage();
            yPos = 20;
          }
          doc.text(lines, 20, yPos);
          yPos += lines.length * 7;
        });
        yPos += 5;
      };
      if (this.feedback.Advantages && this.feedback.Advantages.length > 0) {
        drawSection('Advantages', this.feedback.Advantages, [22, 163, 74]);
      }
      if (this.feedback.Disadvantages && this.feedback.Disadvantages.length > 0) {
        drawSection('Disadvantages', this.feedback.Disadvantages, [220, 38, 38]);
      }
      if (this.feedback.Suggestions && this.feedback.Suggestions.length > 0) {
        drawSection('Suggestions', this.feedback.Suggestions, [202, 138, 4]);
      }
      doc.save('Resume_Analysis_Report.pdf');
    },

    init() {
      if (this.logged) {
        this.startTimer();
        this.checkAdmin();
        this.initDashboard();
      }
    }
  };
}
