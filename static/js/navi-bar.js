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
            toggleBtn.innerHTML = '&#9776;'; // 메뉴 접기 아이콘 (햄버거 아이콘)
        } else {
            navContainer.classList.add('collapsed');
            mainContent.classList.add('expanded');
            toggleBtn.innerHTML = '&#8250;'; // 메뉴 펼치기 아이콘 (오른쪽 화살표)
            toggleBtn.style.right = '10px';
        }
    }

    // 초기 상태 설정
    updateNavState();

    toggleBtn.addEventListener('click', function() {
        toggleNav();
    });

    // 호버 기능 추가
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

    // 이벤트 위임을 사용하여 동적으로 로드된 콘텐츠에도 이벤트 처리
    $(document).on('click', '.toggle-btn', toggleNav);
    
    document.body.addEventListener('click', function(event) {
        if (event.target.matches('.toggle-btn')) {
            toggleNav();
        }
    });
});