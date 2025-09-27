// Navbar dynamic login/logout
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('jwt_token') || sessionStorage.getItem('user_id');
    const logoutLink = document.getElementById('logout-link');
    const loginLink = document.querySelector('a[href="/login"]');
    const registerLink = document.querySelector('a[href="/register"]');

    if (token) {
        logoutLink.style.display = 'block';
        if (loginLink) loginLink.style.display = 'none';
        if (registerLink) registerLink.style.display = 'none';
    } else {
        if (logoutLink) logoutLink.style.display = 'none';
        if (loginLink) loginLink.style.display = 'block';
        if (registerLink) registerLink.style.display = 'block';
    }
});

// Scroll-based animations (Kelina-style fade-in)
const animateOnScroll = () => {
    const elements = document.querySelectorAll('.animate-on-scroll');
    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight * 0.8) {
            el.classList.add('animate__animated', 'animate__fadeInUp');
        }
    });
};

window.addEventListener('scroll', animateOnScroll);
animateOnScroll();

// Form handling
const forms = {
    'register-form': '/api/register',
    'login-form': '/api/login',
    'profile-form': '/api/profile',
    'contact-form': '/api/contact',
    'appointment-form': '/api/appointments',
    'comment-form': '/api/comments'
};

Object.keys(forms).forEach(formId => {
    const form = document.getElementById(formId);
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(form);
            const formObject = {};
            formData.forEach((value, key) => {
                formObject[key] = value;
            });
            
            const response = await fetch(forms[formId], {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': localStorage.getItem('jwt_token') ? `Bearer ${localStorage.getItem('jwt_token')}` : ''
                },
                body: JSON.stringify(formObject)
            });
            const result = await response.json();
            
            if (result.error) {
                alert(result.error);
            } else {
                if (formId === 'login-form') {
                    localStorage.setItem('jwt_token', result.token);
                    sessionStorage.setItem('user_id', result.user_id);
                    window.location.href = '/profile';
                } else if (formId === 'register-form') {
                    alert('Registration successful! Please log in.');
                    window.location.href = '/login';
                } else if (formId === 'appointment-form') {
                    alert('Appointment scheduled successfully!');
                    form.reset();
                } else if (formId === 'contact-form') {
                    alert('Message sent successfully!');
                    form.reset();
                } else if (formId === 'profile-form') {
                    alert('Profile updated successfully!');
                } else if (formId === 'comment-form') {
                    alert('Comment submitted successfully!');
                    form.reset();
                    // Reload comments after submission
                    loadComments();
                }
            }
        });
    }
});

// Load and display comments
function loadComments() {
    const commentsContainer = document.getElementById('comments-container');
    const commentsLoading = document.getElementById('comments-loading');
    
    if (!commentsContainer) return;
    
    // Add a timestamp to prevent caching
    fetch('/get-comments?t=' + new Date().getTime())
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (commentsLoading) {
                commentsLoading.style.display = 'none';
            }
            
            if (data.comments && data.comments.length > 0) {
                const commentsHTML = data.comments.map(comment => `
                    <div class="card mb-3 shadow-sm">
                        <div class="card-body">
                            <h5 class="card-title">${comment.name}</h5>
                            <p class="card-text">${comment.content}</p>
                            <p class="card-text"><small class="text-muted">Posted on ${comment.created_at}</small></p>
                        </div>
                    </div>
                `).join('');
                
                commentsContainer.innerHTML = commentsHTML;
            } else {
                commentsContainer.innerHTML = '<p class="text-center">No comments yet. Be the first to comment!</p>';
            }
        })
        .catch(error => {
            if (commentsLoading) {
                commentsLoading.style.display = 'none';
            }
            commentsContainer.innerHTML = '<p class="text-center text-danger">Failed to load comments. Please try again later.</p>';
            console.error('Error loading comments:', error);
        });
}

// Load comments when the page loads
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('comments-container')) {
        loadComments();
    }
});