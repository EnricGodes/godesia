/**
 * @mention autocomplete functionality
 * Detects @ in text inputs and shows a filterable dropdown of people names
 */

class MentionAutocomplete {
  constructor(inputSelector) {
    this.input = document.querySelector(inputSelector);
    if (!this.input) return;

    this.dropdownContainer = null;
    this.mentionQuery = '';
    this.mentionStart = -1;
    this.people = [];
    this.selectedIndex = -1;

    this.input.addEventListener('input', (e) => this.onInput(e));
    this.input.addEventListener('keydown', (e) => this.onKeydown(e));
    document.addEventListener('click', (e) => this.onDocumentClick(e));
  }

  async loadPeople() {
    if (this.people.length > 0) return;
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      // Get people list - you might need to add a dedicated endpoint
      // For now, we'll fetch from the search endpoint with empty query
      this.people = data.people || [];
    } catch (e) {
      console.error('Failed to load people:', e);
    }
  }

  async searchPeople(query) {
    if (!query) return [];
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      return data.results || [];
    } catch (e) {
      return [];
    }
  }

  onInput(e) {
    const text = this.input.value;
    const cursorPos = this.input.selectionStart;

    // Find @ before cursor
    let atPos = -1;
    for (let i = cursorPos - 1; i >= 0; i--) {
      if (text[i] === '@') {
        atPos = i;
        break;
      } else if (text[i] === ' ' || text[i] === '\n') {
        break;
      }
    }

    if (atPos === -1) {
      this.closeMentionDropdown();
      return;
    }

    this.mentionStart = atPos;
    this.mentionQuery = text.substring(atPos + 1, cursorPos).trim();

    // Only show dropdown if @ is followed by something or space
    if (this.mentionQuery.length === 0 && cursorPos === atPos + 1) {
      this.showMentionDropdown();
      return;
    }

    if (this.mentionQuery.length > 0) {
      this.showMentionDropdown();
    } else {
      this.closeMentionDropdown();
    }
  }

  onKeydown(e) {
    if (!this.dropdownContainer || !this.dropdownContainer.parentElement) return;

    const items = this.dropdownContainer.querySelectorAll('[data-mention-item]');
    if (items.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this.selectedIndex = (this.selectedIndex + 1) % items.length;
        this.updateDropdownSelection(items);
        break;
      case 'ArrowUp':
        e.preventDefault();
        this.selectedIndex = (this.selectedIndex - 1 + items.length) % items.length;
        this.updateDropdownSelection(items);
        break;
      case 'Enter':
      case 'Tab':
        if (this.selectedIndex >= 0 && items[this.selectedIndex]) {
          e.preventDefault();
          const item = items[this.selectedIndex];
          this.selectMention(item.dataset.name);
        }
        break;
      case 'Escape':
        e.preventDefault();
        this.closeMentionDropdown();
        break;
    }
  }

  onDocumentClick(e) {
    if (!this.input.contains(e.target) && this.dropdownContainer && !this.dropdownContainer.contains(e.target)) {
      this.closeMentionDropdown();
    }
  }

  async showMentionDropdown() {
    const results = await this.searchPeople(this.mentionQuery);

    if (results.length === 0) {
      this.closeMentionDropdown();
      return;
    }

    // Create or update dropdown
    if (!this.dropdownContainer) {
      this.dropdownContainer = document.createElement('div');
      this.dropdownContainer.className = 'mention-dropdown';
      this.input.parentElement.appendChild(this.dropdownContainer);
    }

    const itemsHtml = results
      .map(person => {
        let yearText = '';
        if (person.birth_year && person.death_year) {
          yearText = `${person.birth_year}–${person.death_year}`;
        } else if (person.death_year) {
          yearText = `†${person.death_year}`;
        } else if (person.birth_year) {
          yearText = `${person.birth_year}–`;
        }
        return `
          <div class="mention-item" data-mention-item data-name="${person.name}">
            ${person.photo_file ? `<img src="/photos/${person.photo_file}" alt="${person.name}" class="mention-photo">` : `<div class="mention-photo-placeholder">${person.name.charAt(0)}</div>`}
            <div class="mention-info">
              <span class="mention-name">${this.highlightQuery(person.name)}</span>
              ${yearText ? `<span class="mention-years">${yearText}</span>` : ''}
            </div>
          </div>
        `;
      })
      .join('');

    this.dropdownContainer.innerHTML = itemsHtml;
    this.dropdownContainer.style.display = 'block';
    this.selectedIndex = -1;

    // Add click listeners
    this.dropdownContainer.querySelectorAll('[data-mention-item]').forEach(item => {
      item.addEventListener('click', () => {
        this.selectMention(item.dataset.name);
      });
    });

    // Position dropdown
    this.positionDropdown();
  }

  highlightQuery(name) {
    if (!this.mentionQuery) return name;
    const regex = new RegExp(`(${this.mentionQuery})`, 'gi');
    return name.replace(regex, '<strong>$1</strong>');
  }

  selectMention(name) {
    const text = this.input.value;
    const beforeMention = text.substring(0, this.mentionStart);
    const afterMention = text.substring(this.input.selectionStart);

    this.input.value = beforeMention + name + ' ' + afterMention;
    this.input.selectionStart = this.input.selectionEnd = beforeMention.length + name.length + 1;

    this.closeMentionDropdown();
    this.input.focus();
  }

  updateDropdownSelection(items) {
    items.forEach((item, i) => {
      item.classList.toggle('selected', i === this.selectedIndex);
    });

    if (this.selectedIndex >= 0) {
      items[this.selectedIndex].scrollIntoView({ block: 'nearest' });
    }
  }

  closeMentionDropdown() {
    if (this.dropdownContainer) {
      this.dropdownContainer.style.display = 'none';
      this.dropdownContainer.innerHTML = '';
      this.selectedIndex = -1;
    }
  }

  positionDropdown() {
    if (!this.dropdownContainer) return;

    const rect = this.input.getBoundingClientRect();
    const isInInputArea = this.input.closest('.input-area') !== null;

    this.dropdownContainer.style.position = 'fixed';
    this.dropdownContainer.style.left = (rect.left) + 'px';
    this.dropdownContainer.style.width = rect.width + 'px';

    if (isInInputArea) {
      // In chat.html: dropdown above the input
      this.dropdownContainer.style.bottom = 'auto';
      this.dropdownContainer.style.top = (rect.top - 4) + 'px';
      this.dropdownContainer.style.transform = 'translateY(-100%)';
    } else {
      // In index.html: dropdown below the input
      this.dropdownContainer.style.top = (rect.bottom + 4) + 'px';
      this.dropdownContainer.style.bottom = 'auto';
      this.dropdownContainer.style.transform = 'none';
    }
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  // Initialize for chat.html
  if (document.getElementById('question')) {
    new MentionAutocomplete('#question');
  }

  // Initialize for index.html
  if (document.getElementById('hero-query')) {
    new MentionAutocomplete('#hero-query');
  }
});
