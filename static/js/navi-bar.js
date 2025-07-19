document.addEventListener('DOMContentLoaded', function() {
    const navContainer = document.querySelector('.nav-container');
    const mainContent = document.getElementById('main-content');
    const toggleBtn = document.querySelector('.toggle-btn');
    const hoverArea = document.querySelector('.hover-area');
    let isNavExpanded = localStorage.getItem('isNavExpanded') === 'false' ? false : true;
    let isNavLocked = isNavExpanded;

    function toggleNav() {
        isNavExpanded = !isNavExpanded;
        isNavLocked = isNavExpanded;
        localStorage.setItem('isNavExpanded', isNavExpanded);
        updateNavState();
    }

    function updateNavState() {
        if (isNavExpanded) {
            navContainer.classList.remove('collapsed');
            mainContent.classList.remove('expanded');
            toggleBtn.style.right = '0px';
            toggleBtn.innerHTML = '&#9776;'; // Collapse menu icon (hamburger icon)
        } else {
            navContainer.classList.add('collapsed');
            mainContent.classList.add('expanded');
            toggleBtn.innerHTML = '&#8250;'; // Expand menu icon (right arrow)
            toggleBtn.style.right = '10px';
        }
    }

    // Set the initial state
    updateNavState();

    toggleBtn.addEventListener('click', function() {
        toggleNav();
    });

    // Add hover functionality
    hoverArea.addEventListener('mouseenter', function() {
        if (!isNavLocked && !isNavExpanded) {
            navContainer.classList.add('temp-expanded');
        }
    });

    navContainer.addEventListener('mouseleave', function() {
        if (!isNavLocked && !isNavExpanded) {
            navContainer.classList.remove('temp-expanded');
        }
    });

    document.querySelectorAll('.menu-button').forEach(button => {
        button.addEventListener('click', () => {
            const submenuId = button.getAttribute('data-submenu');
            const submenu = document.getElementById(submenuId);
            
            document.querySelectorAll('.submenu').forEach(menu => {
                if (menu.id !== submenuId) {
                    menu.style.maxHeight = null;
                }
            });

            if (submenu.style.maxHeight) {
                submenu.style.maxHeight = null;
            } else {
                submenu.style.maxHeight = submenu.scrollHeight + "px";
            }
        });
    });

    // Use event delegation to handle events on dynamically loaded content
    $(document).on('click', '.toggle-btn', toggleNav);
    
    document.body.addEventListener('click', function(event) {
        if (event.target.matches('.toggle-btn')) {
            toggleNav();
        }
    });
});