const resumeInput = document.getElementById("resumes");
const fileNames = document.getElementById("fileNames");
const filterForm = document.getElementById("filterForm");
const submitBtn = document.getElementById("submitBtn");

if (resumeInput && fileNames) {
  resumeInput.addEventListener("change", () => {
    const files = Array.from(resumeInput.files || []);
    fileNames.textContent = files.length ? files.map(file => file.name).join(", ") : "No files selected";
  });
}
if (filterForm && submitBtn) {
  filterForm.addEventListener("submit", () => {
    submitBtn.textContent = "Processing resumes...";
    submitBtn.disabled = true;
  });
}
