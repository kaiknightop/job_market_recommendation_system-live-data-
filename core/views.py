from django.shortcuts import render, redirect
from .jobapi import fetch_jobs_from_jooble
from .models import Profile
from django.contrib.auth import authenticate, login, logout
from .forms import RegisterForm
import os
from .forms import LoginForm
from django.contrib.auth.decorators import login_required #restricting access to home page
from .forms import UserUpdateForm, ProfileUpdateForm
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import precision_score, recall_score, f1_score
from sklearn.feature_extraction.text import CountVectorizer
import re 
from .models import UserJobInteraction
from django.utils.timezone import now
from django.http import HttpResponseRedirect
from django.db.models import Q
from .models import Job
from django.conf import settings
from django.http import HttpResponse
from dotenv import load_dotenv

load_dotenv()


@login_required
def home(request):
    jobs = []

    if request.user.is_authenticated:
        try:
            profile = Profile.objects.get(user=request.user)
            skills = profile.skills
            location = profile.location

            print("== USER PROFILE ==")
            print("Skills:", skills)
            print("Location:", location)

            result = fetch_jobs_from_jooble(keywords=skills, location=location)
            job_data = result if result else []
            print("== RAW API RESPONSE ==")
            print(job_data)
            print("🔍 FINAL JOB LIST LENGTH:", len(job_data))

            if job_data and skills:
                # 🧹 CLEAN the snippets
                for job in job_data:
                    if 'snippet' in job and job['snippet']:
                        snippet = job['snippet']
                        # Remove HTML tags
                        snippet = re.sub('<.*?>', '', snippet)
                        # Replace &nbsp; with space
                        snippet = snippet.replace('&nbsp;', ' ')
                        job['snippet'] = snippet

                # Now do TF-IDF recommendation
                job_descriptions = [job.get('title', '') + ' ' + job.get('snippet', '') for job in job_data]

                vectorizer = TfidfVectorizer(stop_words='english')
                job_matrix = vectorizer.fit_transform(job_descriptions)
                user_vector = vectorizer.transform([skills])

                scores = cosine_similarity(user_vector, job_matrix)[0]
                top_indices = scores.argsort()[::-1][:10]
                jobs = [job_data[i] for i in top_indices]

                if jobs:
                    print("Sample Cleaned Job:", jobs[0])
            else:
                print("No job data or no skills.")
                jobs = job_data

        except Profile.DoesNotExist:
            print("Profile not found")

    return render(request, 'home.html', {'jobs': jobs})



def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            login(request, user)  # Log in the user automatically
            return redirect('home')  # Redirect to home page
    else:
        form = RegisterForm()
    
    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')  # Redirect to home page after login
            else:
                return render(request, 'login.html', {'form': form, 'error': 'Invalid username or password'})
    else:
        form = LoginForm()
    
    return render(request, 'login.html', {'form': form})

def user_logout(request):
    logout(request)
    return redirect('login')  # Redirect to login page after logout

@login_required
def profile(request):
    try:
        # Check if user has a profile
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = None  # Avoid redirection; just handle the missing profile gracefully

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect('profile')

    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    # Pass the profile object to the template for display
    return render(request, 'profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'profile': profile
    })


@login_required
def edit_profile(request):
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect('profile')  # Redirect back to profile page

    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)

    return render(request, 'edit_profile.html', {'user_form': user_form, 'profile_form': profile_form})



@login_required
def track_job_click(request):
    job_title = request.GET.get('title')
    job_link = request.GET.get('link')
    company = request.GET.get('company', '')
    location = request.GET.get('location', '')

    if job_title and job_link:
        # Save the interaction
        UserJobInteraction.objects.create(
            user=request.user,
            job_title=job_title,
            job_link=job_link,
            company_name=company,
            location=location,
            interaction_type='viewed',
            timestamp=now()
        )

    return HttpResponseRedirect(job_link)


@login_required
def similar_users_recommendations(request):
    user = request.user

    # Get job titles this user has already interacted with
    user_jobs = UserJobInteraction.objects.filter(user=user).values_list('job_title', flat=True)

    # Get users who interacted with the same jobs
    similar_users = UserJobInteraction.objects.filter(
        job_title__in=user_jobs
    ).exclude(user=user).values_list('user', flat=True).distinct()

    # Get jobs those similar users have seen, but this user hasn’t
    recommended_jobs = UserJobInteraction.objects.filter(
        user__in=similar_users
    ).exclude(job_title__in=user_jobs).distinct('job_title')

    return render(request, 'similar_users.html', {'recommended_jobs': recommended_jobs})


@login_required
def record_job_click(request):
    if request.method == 'GET':
        job_title = request.GET.get('title')
        job_link = request.GET.get('link')
        location = request.GET.get('location', '')
        company_name = request.GET.get('company', '')

        if job_title and job_link:
            # Save interaction
            UserJobInteraction.objects.get_or_create(
                user=request.user,
                job_title=job_title,
                job_link=job_link,
                location=location,
                company_name=company_name
            )

            return HttpResponseRedirect(job_link)
    return redirect('home')


@login_required
def similar_users_jobs(request):
    user = request.user

    # Get all interactions
    interactions = UserJobInteraction.objects.all()

    # Create user-job interaction mapping
    data = {}
    for interaction in interactions:
        data.setdefault(interaction.user.username, []).append(interaction.job_title)

    # Create a list of all users and documents of their job titles
    users = list(data.keys())
    documents = [' '.join(titles) for titles in data.values()]

    # Vectorize the job titles
    vectorizer = CountVectorizer()
    user_matrix = vectorizer.fit_transform(documents)

    # Compute similarity
    sim_matrix = cosine_similarity(user_matrix)

    # Find index of current user
    try:
        current_index = users.index(user.username)
    except ValueError:
        return render(request, 'similar_users.html', {'similar_jobs': []})

    # Get similarity scores and find top similar users
    sim_scores = list(enumerate(sim_matrix[current_index]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)[1:4]  # top 3 others

    # Collect jobs from similar users
    similar_jobs = []
    for idx, score in sim_scores:
        similar_username = users[idx]
        similar_user_jobs = data[similar_username]
        similar_jobs.extend(similar_user_jobs)

    # Remove duplicates and return
    similar_jobs = list(set(similar_jobs))
    return render(request, 'similar_users.html', {'similar_jobs': similar_jobs})


def search_jobs(request):
    keyword = request.GET.get('keyword', '')
    similar_jobs = []
    api_jobs = []

    if keyword:
        # Local DB search
        similar_jobs = Job.objects.filter(title__icontains=keyword)

        # Jooble API search
        url = "https://jooble.org/api/"
        key = os.getenv("JOOBLE_API_KEY")
        payload = {"keywords": keyword, "location": ""}
        response = requests.post(url + key, json=payload)

        if response.status_code == 200:
            data = response.json()
            api_jobs = data.get('jobs', [])
        else:
            print("Jooble API Error:", response.text)

    return render(request, "recommend_jobs.html", {
        "keyword": keyword,
        "similar_jobs": similar_jobs,
        "api_jobs": api_jobs
    })


@login_required
def evaluate_system(request):
    user = request.user

    #GET recommendations from home logic 
    profile = Profile.objects.get(user=user)
    skills = profile.skills
    location = profile.location

    result = fetch_jobs_from_jooble(keywords=skills, location=location)
    job_data = result if result else []

    recommended_titles = []
    if job_data and skills:
        # Clean and vectorize as in home()
        for job in job_data:
            if 'snippet' in job and job['snippet']:
                snippet = job['snippet']
                snippet = re.sub('<.*?>', '', snippet)
                snippet = snippet.replace('&nbsp;', ' ')
                job['snippet'] = snippet

        job_descriptions = [job.get('title', '') + ' ' + job.get('snippet', '') for job in job_data]

        vectorizer = TfidfVectorizer(stop_words='english')
        job_matrix = vectorizer.fit_transform(job_descriptions)
        user_vector = vectorizer.transform([skills])

        scores = cosine_similarity(user_vector, job_matrix)[0]
        top_indices = scores.argsort()[::-1][:10]
        recommended_jobs = [job_data[i] for i in top_indices]

        recommended_titles = [job['title'] for job in recommended_jobs]

    #GET jobs the user actually interacted with
    interacted_titles = list(UserJobInteraction.objects.filter(user=user).values_list('job_title', flat=True))

    #BUILD y_true and y_pred
    y_true = [1 if title in interacted_titles else 0 for title in recommended_titles]
    y_pred = [1]*len(recommended_titles)  # system predicts all recommended as positive

    # Avoid empty data error
    if not y_true:
        y_true = [0]
        y_pred = [0]

    #CALCULATE METRICS
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    print("Evaluation Results")
    print(f"Precision: {precision:.2f}")
    print(f"Recall: {recall:.2f}")
    print(f"F1 Score: {f1:.2f}")

    return render(request, 'evaluation.html', {
        'precision': precision,
        'recall': recall,
        'f1': f1
    })
