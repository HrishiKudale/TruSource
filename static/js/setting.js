(function () {
  const $ = (id) => document.getElementById(id);

  // overlays
  const editOverlay = $("editProfileOverlay");
  const pwOverlay = $("passwordOverlay");

  // open buttons
  const openEdit = $("openEditProfile");
  const openPw = $("openChangePassword");

  // close buttons
  const editCancel = $("editCancelBtn");
  const pwCancel = $("pwCancelBtn");

  // actions
  const editSave = $("editSaveBtn");
  const pwSave = $("pwSaveBtn");

  // docs upload buttons (small ⤓ buttons)
  const docButtons = document.querySelectorAll('button[data-doc]');

  function show(overlay) {
    overlay.classList.add("show");
    overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function hide(overlay) {
    overlay.classList.remove("show");
    overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function overlayCloseOnOutside(overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) hide(overlay);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && overlay.classList.contains("show")) hide(overlay);
    });
  }

  if (openEdit && editOverlay) openEdit.addEventListener("click", () => show(editOverlay));
  if (openPw && pwOverlay) openPw.addEventListener("click", () => show(pwOverlay));

  if (editCancel && editOverlay) editCancel.addEventListener("click", () => hide(editOverlay));
  if (pwCancel && pwOverlay) pwCancel.addEventListener("click", () => hide(pwOverlay));

  if (editOverlay) overlayCloseOnOutside(editOverlay);
  if (pwOverlay) overlayCloseOnOutside(pwOverlay);

  // avatar preview in edit profile modal
  const photoInput = $("profilePhotoFile");
  const photoPreview = $("editAvatarPreview");
  if (photoInput && photoPreview) {
    photoInput.addEventListener("change", () => {
      const f = photoInput.files && photoInput.files[0];
      if (!f) return;
      photoPreview.src = URL.createObjectURL(f);
    });
  }

  // save profile
  if (editSave) {
    editSave.addEventListener("click", async () => {
      editSave.disabled = true;

      try {
        const fd = new FormData();
        fd.append("name", $("editName").value || "");
        fd.append("email", $("editEmail").value || "");
        fd.append("phone", $("editPhone").value || "");

        const img = photoInput && photoInput.files && photoInput.files[0];
        if (img) fd.append("profilePhoto", img);

        const res = await fetch("/settings/profile", {
          method: "POST",
          credentials: "include",
          body: fd
        });

        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.message || "Update failed");

        window.location.reload();
      } catch (e) {
        alert(e.message || "Profile update failed");
        editSave.disabled = false;
      }
    });
  }

  // toggle password eye
  document.querySelectorAll(".pw-eye").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-eye");
      const input = document.getElementById(id);
      if (!input) return;
      input.type = input.type === "password" ? "text" : "password";
    });
  });

  // change password
  if (pwSave) {
    pwSave.addEventListener("click", async () => {
      pwSave.disabled = true;

      try {
        const currentPassword = $("currentPassword").value || "";
        const newPassword = $("newPassword").value || "";
        const confirmPassword = $("confirmPassword").value || "";

        const res = await fetch("/settings/password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ currentPassword, newPassword, confirmPassword })
        });

        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.message || "Password update failed");

        alert("Password updated successfully");
        window.location.reload();
      } catch (e) {
        alert(e.message || "Password update failed");
        pwSave.disabled = false;
      }
    });
  }

  // documents upload
  docButtons.forEach(btn => {
    btn.addEventListener("click", async () => {
      const key = btn.getAttribute("data-doc"); // aadhaar | khasar
      const input = key === "aadhaar" ? $("aadhaarFile") : $("khasarFile");
      const meta = key === "aadhaar" ? $("aadhaarMeta") : $("khasarMeta");

      const f = input && input.files && input.files[0];
      if (!f) return alert("Please choose a file first");

      const fd = new FormData();
      fd.append("docKey", key);
      fd.append("file", f);

      btn.disabled = true;

      try {
        const res = await fetch("/settings/documents", {
          method: "POST",
          credentials: "include",
          body: fd
        });

        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.message || "Upload failed");

        if (meta) meta.textContent = data.filename || "uploaded";
      } catch (e) {
        alert(e.message || "Upload failed");
      } finally {
        btn.disabled = false;
      }
    });
  });

  // preferences
  const lang = $("languageSelect");
  const notif = $("notifToggle");

  async function savePrefs(patch) {
    const res = await fetch("/settings/preferences", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(patch)
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.message || "Failed");
  }

  if (lang) {
    lang.addEventListener("change", async () => {
      try {
        await savePrefs({ language: lang.value });
      } catch (e) {
        alert(e.message);
      }
    });
  }

  if (notif) {
    notif.addEventListener("change", async () => {
      try {
        await savePrefs({ harvestNotifications: !!notif.checked });
      } catch (e) {
        alert(e.message);
      }
    });
  }
})();
