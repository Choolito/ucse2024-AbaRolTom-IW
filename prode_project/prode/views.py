import pdb
from pyexpat.errors import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from prode.models import Grupo, Partido, Prediccion
from prode.forms import PrediccionForm
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, F, Q
from prode.utils import calcular_ranking_global, calcular_ranking_grupo
from django.db.models import Count, Case, When, IntegerField
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from haystack.query import SearchQuerySet
from django.core.management import call_command
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Case, When, IntegerField, F
from .models import ChatShowMessagesSerializer, Partido, Prediccion, ChatMessage, ChatMessageSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response

def lista_partidos(request):
    # Obtener la fecha actual de la liga
    fecha_liga = request.GET.get('fecha_liga')
    current_fecha = int(fecha_liga) if fecha_liga else 0

    # Asegurarse de que current_fecha esté dentro del rango válido
    current_fecha = max(0, min(current_fecha, 27))

    # Filtrar partidos por fecha de la liga
    if current_fecha == 0:
        partidos = Partido.objects.all().order_by('fecha_liga', 'fecha')
    else:
        partidos = Partido.objects.filter(fecha_liga=current_fecha).order_by('fecha')

    # Implementación del buscador global
    query = request.GET.get('q', '')
    results = SearchQuerySet().filter(content=query) if query else None

    # Implementación de los filtros (equipo, fecha y hora)
    equipo = request.GET.get('equipo')
    fecha = request.GET.get('fecha')
    hora = request.GET.get('hora')

    # Filtrar por equipo
    if equipo:
        partidos = partidos.filter(
            Q(equipo_local__nombre__icontains=equipo) | 
            Q(equipo_visitante__nombre__icontains=equipo)
        )

    # Filtrar por fecha
    if fecha:
        partidos = partidos.filter(fecha__date=fecha)

    # Filtrar por hora
    if hora:
        partidos = partidos.filter(fecha__time__startswith=hora)

    # Si el usuario está autenticado, buscar sus predicciones
    usuario = request.user
    predicciones_usuario = {}
    if usuario.is_authenticated:
        predicciones_usuario = {
            prediccion.partido.id: prediccion 
            for prediccion in Prediccion.objects.filter(usuario=usuario, partido__in=partidos)
        }

    # Crear un diccionario para verificar si el tiempo límite ha pasado para cada partido
    tiempos_limite = {}
    ahora = timezone.now()
    for partido in partidos:
        tiempo_limite = partido.fecha - timezone.timedelta(hours=1)
        if ahora > tiempo_limite:
            tiempos_limite[partido.id] = True
        
        # Actualizar el estado del partido
        tiempo_restante = (partido.fecha - ahora).total_seconds() / 60
        if tiempo_restante > 60:
            partido.status = 'Programado'
        elif tiempo_restante > 0:
            partido.status = 'Por comenzar'
        elif tiempo_restante > -105:
            partido.status = 'En juego'
        else:
            partido.status = 'Finalizado'

    # Calcular fecha anterior y siguiente
    fecha_anterior = max(0, current_fecha - 1)
    fecha_siguiente = min(27, current_fecha + 1)

    for partido in partidos:
        total_predicciones = Prediccion.objects.filter(partido=partido).count()
        if total_predicciones > 0:
            estadisticas = Prediccion.objects.filter(partido=partido).aggregate(
                victoria_local=Count(Case(When(prediccion_local__gt=F('prediccion_visitante'), then=1), output_field=IntegerField())),
                victoria_visitante=Count(Case(When(prediccion_visitante__gt=F('prediccion_local'), then=1), output_field=IntegerField())),
                empate=Count(Case(When(prediccion_local=F('prediccion_visitante'), then=1), output_field=IntegerField()))
            )
            partido.estadisticas = {
                'local': round((estadisticas['victoria_local'] / total_predicciones) * 100, 1),
                'visitante': round((estadisticas['victoria_visitante'] / total_predicciones) * 100, 1),
                'empate': round((estadisticas['empate'] / total_predicciones) * 100, 1)
            }
        else:
            partido.estadisticas = {'local': 0, 'visitante': 0, 'empate': 0}

    context = {
        'partidos': partidos,
        'predicciones_usuario': predicciones_usuario,
        'tiempos_limite': tiempos_limite,  
        'rango_fechas': range(1, 28),
        'current_fecha': current_fecha,
        'fecha_anterior': fecha_anterior,
        'fecha_siguiente': fecha_siguiente,
        'query': query,
        'results': results  # Para el buscador global
    }

    return render(request, 'prode/lista_partidos.html', context)

@login_required
def detalle_partido(request, partido_id):
    partido = get_object_or_404(Partido, id=partido_id)
    usuario = request.user
    
    # Comprobar si el usuario ya ha realizado una predicción para este partido
    prediccion_existente = Prediccion.objects.filter(partido=partido, usuario=usuario).first()

    # Verificar si la hora del partido - 1 hora es mayor a la hora actual
    tiempo_limite = partido.fecha - timezone.timedelta(hours=1)
    tiempo_limite_pasado = timezone.now() > tiempo_limite

    if request.method == 'POST' and not prediccion_existente and not tiempo_limite_pasado:
        prediccion_local = request.POST.get('prediccion_local')
        prediccion_visitante = request.POST.get('prediccion_visitante')

        Prediccion.objects.create(
            partido=partido,
            usuario=usuario,
            prediccion_local=prediccion_local,
            prediccion_visitante=prediccion_visitante
        )
        return redirect('detalle_partido', partido_id=partido.id)

    # Calcular estadísticas de predicciones
    predicciones = Prediccion.objects.filter(partido=partido)
    total_predicciones = predicciones.count()

    if total_predicciones > 0:
        resultados = predicciones.aggregate(
            victoria_local=Count(Case(When(prediccion_local__gt=F('prediccion_visitante'), then=1), output_field=IntegerField())),
            empate=Count(Case(When(prediccion_local=F('prediccion_visitante'), then=1), output_field=IntegerField())),
            victoria_visitante=Count(Case(When(prediccion_local__lt=F('prediccion_visitante'), then=1), output_field=IntegerField()))
        )
        
        porcentaje_victoria_local = (resultados['victoria_local'] / total_predicciones) * 100
        porcentaje_empate = (resultados['empate'] / total_predicciones) * 100
        porcentaje_victoria_visitante = (resultados['victoria_visitante'] / total_predicciones) * 100
    else:
        porcentaje_victoria_local = porcentaje_empate = porcentaje_victoria_visitante = 0

    context = {
        'partido': partido,
        'usuario': usuario,
        'prediccion_existente': prediccion_existente,
        'tiempo_limite_pasado': tiempo_limite_pasado,
        'total_predicciones': total_predicciones,
        'porcentaje_victoria_local': porcentaje_victoria_local,
        'porcentaje_victoria_visitante': porcentaje_victoria_visitante,
        'porcentaje_empate': porcentaje_empate,
        'chat_api_url': f"/chat/{partido_id}/"  # URL de la API del chat
    }
    return render(request, 'prode/detalle_partido.html', context)

@login_required
def ranking_global(request):
    # Obtener el ranking global
    usuarios_con_puntaje = calcular_ranking_global()

    context = {
        'usuarios_con_puntaje': usuarios_con_puntaje,
    }
    return render(request, 'prode/ranking_global.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def crear_grupo(request):
    # Fetch the groups created by the user
    grupos_creados = Grupo.objects.filter(creador=request.user)

    # Fetch the groups where the user is a member but not the creator
    grupos_unidos = Grupo.objects.filter(miembros=request.user).exclude(creador=request.user)

    if request.method == 'POST':
        nombre = request.POST.get('nombre_grupo')
        descripcion = request.POST.get('descripcion_grupo', '')
        privacidad = request.POST.get('privacidad_grupo', 'publico')

        try:
            grupo = Grupo.objects.create(
                nombre=nombre,
                descripcion=descripcion,
                privacidad=privacidad,
                creador=request.user
            )
            grupo.miembros.add(request.user)
            url_invitacion = request.build_absolute_uri(f'/unirse_grupo/{grupo.codigo_invitacion}/')
            
            return JsonResponse({
                'success': True,
                'grupo': {
                    'id': grupo.id,
                    'nombre': grupo.nombre,
                    'descripcion': grupo.descripcion,
                    'privacidad': grupo.get_privacidad_display(),
                    'creador': grupo.creador.username,
                    'miembros': [miembro.username for miembro in grupo.miembros.all()],
                    'url_invitacion': url_invitacion
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    context = {
        'grupos_creados': grupos_creados,
        'grupos_unidos': grupos_unidos
    }
    return render(request, 'prode/crear_grupo.html', context)

@login_required
def detalle_grupo(request, grupo_id):
    # Obtener el grupo o devolver un 404 si no existe
    grupo = get_object_or_404(Grupo, id=grupo_id)

    # Construir la URL de invitación utilizando el código de invitación
    url_invitacion = request.build_absolute_uri(f'/unirse_grupo/{grupo.codigo_invitacion}/')

    context = {
        'grupo': grupo,
        'url_invitacion': url_invitacion
    }

    return render(request, 'prode/detalle_grupo.html', context)

@login_required
def unirse_grupo(request, codigo_invitacion):
    grupo = get_object_or_404(Grupo, codigo_invitacion=codigo_invitacion)

    if request.user not in grupo.miembros.all():
        grupo.miembros.add(request.user)

    return redirect('detalle_grupo', grupo_id=grupo.id)

@login_required
def ranking_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, id=grupo_id)
    ranking = calcular_ranking_grupo(grupo_id)
    
    context = {
        'grupo': grupo,
        'ranking': ranking,
    }
    return render(request, 'prode/ranking_grupo.html', context)

@login_required
def salir_grupo(request, grupo_id):
    if request.method == 'POST':
        grupo = get_object_or_404(Grupo, id=grupo_id)
        if request.user in grupo.miembros.all():
            if request.user != grupo.creador:
                grupo.miembros.remove(request.user)
                messages.success(request, f"Has salido del grupo '{grupo.nombre}'.")
            else:
                messages.error(request, "No puedes salir del grupo que has creado.")
        else:
            messages.error(request, "No eres miembro de este grupo.")
        return redirect('crear_grupo')
    return redirect('detalle_grupo', grupo_id=grupo_id)

def buscar_partidos(request):
    query = request.GET.get('q', '')  # Recupera el valor del input de búsqueda
    
    # Filtra partidos por el equipo local o visitante que coincida con la búsqueda
    partidos = Partido.objects.filter(
        Q(equipo_local__nombre__icontains=query) | Q(equipo_visitante__nombre__icontains=query)
    )
    
    # Renderiza el template de lista de partidos, enviando los partidos filtrados
    return render(request, 'prode/lista_partidos.html', {'partidos': partidos, 'query': query, 'rango_fechas': range(1, 28),})

def robots_txt(request):
    lines = [
        "User-Agent: *",
        "Disallow: /admin/",
        "Allow: /",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def rebuild_index(request):
    try:
        call_command('rebuild_index', interactive=False)
        result = "Index rebuilt successfully."
    except Exception as e:
        result = f"Error: {e}"

    return JsonResponse({"result": result})

@api_view(['GET', 'POST'])
def chat_view(request, partido_id):
    if request.method == 'POST':
        data = {
            'partido': partido_id,
            'usuario': request.user.id,
            'mensaje': request.data['mensaje']
        }
        serializer = ChatMessageSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
    else:
        messages = ChatMessage.objects.filter(partido_id=partido_id)
        serializer = ChatShowMessagesSerializer(messages, many=True)
        return Response(serializer.data)