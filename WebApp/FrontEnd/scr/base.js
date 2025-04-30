document.addEventListener('DOMContentLoaded', function() {
      const profile = document.getElementById('profileDropdown');
      const dropdown = profile.querySelector('.dropdown-menu');

      profile.addEventListener('click', function(e) {
        e.stopPropagation();
        dropdown.classList.toggle('show');
      });

      document.addEventListener('click', function() {
        dropdown.classList.remove('show');
      });
    });