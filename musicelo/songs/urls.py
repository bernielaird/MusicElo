from django.urls import path

from . import views

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("add/",views.add,name = "add"),
    #path("add/<str:lz_uri>",views.add,name = "add"),
    # r'^get_item/$'
    path("songlist",views.songlist,name = "songlist"),
    path("ratinglist",views.ratinglist,name = "ratinglist"),
    path("versus",views.versus,name = "versus"),
    path("versus/edit/<str:first>/<str:second>",views.versus_edit,name = "versus_edit"),
]