async function fetchDocuments() {
  const resp = await fetch('/api/ops/knowledge-base');
  const docs = await resp.json();
  const tbody = document.querySelector('#kb-table tbody');
  tbody.innerHTML = '';
  docs.forEach(d => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><a href="${d.url}">${d.filename}</a></td>
      <td>${d.description || ''}</td>
      <td>${new Date(d.uploaded_at).toLocaleString()}</td>
      <td>
        <button data-id="${d.id}" class="delete-btn">Удалить</button>
      </td>`;
    tbody.append(tr);
  });
  // повесим обработчики на кнопки «Удалить»
  document.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', async e => {
      const id = e.target.dataset.id;
      if (!confirm('Уверены?')) return;
      await fetch(`/api/ops/knowledge-base/${id}`, { method: 'DELETE' });
      fetchDocuments();  // перезагрузить список
    });
  });
}

// при загрузке страницы
document.addEventListener('DOMContentLoaded', fetchDocuments);
