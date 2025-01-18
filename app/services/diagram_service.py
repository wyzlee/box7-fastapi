import os
import json
import aiofiles
from typing import Dict, List, Optional
from fastapi import WebSocket
from crewai import Agent, Crew, Task, Process
from ..utils.crewai_functions import choose_llm, choose_tool, reset_chroma
from ..utils.pdf_utils import extract_page_text_from_file
import networkx as nx
from ..websocket.manager import manager

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
MAGENTA = '\033[35m'
END = '\033[0m'

async def crewai_summarize_if_not_exists(pdf: str, pages: int = 6, history: Optional[str] = None, llm: str = "openai") -> str:
    """
    Récupère ou génère le résumé d'un document PDF de manière asynchrone.
    
    Args:
        pdf (str): Chemin vers le fichier PDF
        pages (int): Nombre de pages à traiter
        history (Optional[str]): Historique des interactions (non utilisé pour l'instant)
        llm (str): Modèle de langage à utiliser
        
    Returns:
        str: Résumé du document
    """
    txt_path = f"{pdf}.txt"
    if os.path.exists(txt_path):
        try:
            async with aiofiles.open(txt_path, "r", encoding="utf-8") as file:
                return await file.read()
        except Exception as e:
            print(f"Erreur lors de la lecture du fichier : {e}")
            return await crewai_summarize(pdf, pages=pages, history=history, llm=llm)
    else:
        print(f"Le fichier {pdf} n'existe pas, on le génère.")
        return await crewai_summarize(pdf, pages=pages, history=history, llm=llm)

async def crewai_summarize(pdf: str, pages: int = -1, history: Optional[str] = None, llm: str = "openai") -> str:
    """
    Génère un résumé d'un document PDF en utilisant CrewAI de manière asynchrone.
    
    Args:
        pdf (str): Chemin vers le fichier PDF
        pages (int): Nombre de pages à traiter (-1 pour tout le document)
        history (Optional[str]): Historique des interactions (non utilisé pour l'instant)
        llm (str): Modèle de langage à utiliser
        
    Returns:
        str: Résumé généré par CrewAI
    """
    # Extraction du texte de toutes les pages


    print(f"{MAGENTA}Starting CrewAI summarization with LLM: {llm}{END}")
    all_pages = await extract_page_text_from_file(src=pdf)
    
    # Détermination du nombre de pages à traiter
    if pages <= 0:
        pages = len(all_pages)
    else:
        pages = min(pages, len(all_pages))
    
    # Estimation approximative des tokens (environ 200 tokens par page en moyenne)
    tokens_per_chunk = 2000  # Limite conservative pour éviter les dépassements
    pages_per_chunk = max(1, tokens_per_chunk // 200)
    
    # Traitement par chunks
    chunks = []
    for i in range(0, pages, pages_per_chunk):
        end_idx = min(i + pages_per_chunk, pages)
        chunk_pages = all_pages[i:end_idx]
        chunk_text = "\n".join(chunk_pages)
        chunks.append(chunk_text)
    
    # Traitement de chaque chunk
    chunk_summaries = []
    for chunk_idx, chunk in enumerate(chunks):
        # Définition des agents pour ce chunk
        agents = {
            "title_extractor": Agent(
                name=f"Extracteur de Titres - Partie {chunk_idx + 1}",
                role="Expert en identification de titres",
                goal="Identifier les titres et thèmes principaux de cette section",
                backstory="Un spécialiste dans l'identification rapide de titres et de sujets principaux.",
                llm=choose_llm(llm)
            ),
            "content_analyzer": Agent(
                name=f"Analyseur de Contenu - Partie {chunk_idx + 1}",
                role="Expert en analyse de contenu",
                goal="Analyser et résumer le contenu de cette section",
                backstory="Un expert en analyse et synthèse de texte, capable d'extraire les informations essentielles.",
                llm=choose_llm(llm),
                verbose=True
            )
        }

        # Définition des tâches pour ce chunk
        tasks = [
            Task(
                name=f"Analyse des Titres - Partie {chunk_idx + 1}",
                agent=agents["title_extractor"],
                description=f"Identifie les titres et thèmes principaux de cette section:\n{chunk}",
                expected_output="Les titres et thèmes principaux en français."
            ),
            Task(
                name=f"Analyse du Contenu - Partie {chunk_idx + 1}",
                agent=agents["content_analyzer"],
                description=f"Analyse et résume cette section du document:\n{chunk}",
                expected_output="Un résumé structuré en français avec les informations clés au format markdown."
            )
        ]

        # Création et exécution du crew pour ce chunk
        crew = Crew(
            agents=list(agents.values()),
            tasks=tasks,
            process=Process.sequential
        )

        result = await crew.kickoff_async()
        chunk_summaries.append(result.raw)

    # Si nous avons plusieurs chunks, créons un résumé final
    if len(chunk_summaries) > 1:
        final_agents = {
            "synthesizer": Agent(
                name="Synthétiseur Final",
                role="Expert en synthèse globale",
                goal="Créer une synthèse cohérente de l'ensemble du document",
                backstory="Un expert en synthèse capable de combiner plusieurs résumés en un ensemble cohérent.",
                llm=choose_llm(llm),
                verbose=True
            )
        }

        final_tasks = [
            Task(
                name="Synthèse Finale",
                agent=final_agents["synthesizer"],
                description=f"Crée une synthèse cohérente à partir des résumés suivants:{chr(10)}{chr(10).join(['---'] + chunk_summaries)}",
                expected_output="Une synthèse globale structurée en français au format markdown, incluant les points clés de chaque section."
            )
        ]

        final_crew = Crew(
            agents=list(final_agents.values()),
            tasks=final_tasks,
            process=Process.sequential
        )

        final_result = await final_crew.kickoff_async()
        result_str = final_result.raw
    else:
        result_str = chunk_summaries[0]

    # Sauvegarde du résultat
    txt_path = f"{pdf}.txt"
    async with aiofiles.open(txt_path, "w", encoding="utf-8") as file:
        await file.write(result_str)

    return result_str


async def crewai_summarize_old(pdf: str, pages: int = 6, history: Optional[str] = None, llm: str = "openai") -> str:
    """
    Génère un résumé d'un document PDF en utilisant CrewAI de manière asynchrone.
    
    Args:
        pdf (str): Chemin vers le fichier PDF
        pages (int): Nombre de pages à traiter
        history (Optional[str]): Historique des interactions (non utilisé pour l'instant)
        llm (str): Modèle de langage à utiliser
        
    Returns:
        str: Résumé généré par CrewAI
    """
    firstpages = await extract_page_text_from_file(src=pdf)
    try:
        content = "\n".join(firstpages[:int(pages)])
    except ValueError:
        content = "\n".join(firstpages[:6])

    # Définition des agents
    agents = {
        "title_extractor": Agent(
            name="Extracteur de Titres",
            role="Expert en identification de titres",
            goal="Identifier le titre du document",
            backstory="Un spécialiste dans l'identification rapide de titres et de sujets principaux à partir d'extraits de documents textuels.",
            llm=choose_llm(llm)
        ),
        "author_audience_extractor": Agent(
            name="Extracteur d'Auteurs et de Public Cible",
            role="Expert en analyse d'auteur et de public cible",
            goal="Identifier qui a écrit le document et à qui il est adressé",
            backstory="Un analyste expérimenté capable de déduire l'auteur et le public cible d'un texte en étudiant le style et le contenu.",
            llm=choose_llm(llm)
        ),
        "subject_purpose_extractor": Agent(
            name="Extracteur de Sujets et d'Objectifs",
            role="Expert en analyse de contenu",
            goal="Déterminer le sujet du document et son but",
            backstory="Un expert en compréhension et analyse de texte, capable de résumer les thèmes principaux et les objectifs sous-jacents d'un document.",
            llm=choose_llm(llm)
        )
    }

    # Définition des tâches
    tasks = [
        Task(
            name="Extraction du Titre",
            agent=agents["title_extractor"],
            description=f"À partir du texte suivant, identifie le titre du document :\n{content}",
            expected_output="Le titre du document en français."
        ),
        Task(
            name="Identification de l'Auteur et du Public Cible",
            agent=agents["author_audience_extractor"],
            description=f"En te basant sur le texte suivant, détermine qui a écrit le document et à quel public il s'adresse :\n{content}",
            expected_output="L'auteur du document et le public cible en français."
        ),
        Task(
            name="Analyse du Sujet et de l'Objectif",
            agent=agents["subject_purpose_extractor"],
            description=f"Analyse le texte suivant pour déterminer le sujet du document et son objectif :\n{content}",
            expected_output="Le sujet et l'objectif du document en français avec un titre des sous-titres les informations clés (chiffres conclusions) et structuré au format markdown."
        )
    ]

    # Création et exécution du crew
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential
    )

    result = await crew.kickoff_async()
    result_str = result.raw

    # Sauvegarde du résultat
    txt_path = f"{pdf}.txt"
    async with aiofiles.open(txt_path, "w", encoding="utf-8") as file:
        await file.write(result_str)

    return result_str


async def generate_diagram_check_structure(diagramData, llm):
    """
    Check the structure of the diagramData and return a json
    """
    # Définir les tâches

    print(f"{MAGENTA}Starting CrewAI diagram structure check with LLM: {llm}{END}")

    diagram_expert = Agent(
            role='Expert en Conception de Diagrammes',
            goal="""Vérifier la structure d'un diagramme à partir du json qui le représente""",
            backstory="""Vous êtes un expert dans la création de diagrammes qui représentent des workflows complexes. 
            Vous excellez dans l'identification des agents clés, leurs rôles et les relations entre eux.""",
            verbose=True,
            allow_delegation=False,
            llm=choose_llm(llm)
        )
    

    create_diagram = Task(
        description=f"""À partir de l'analyse du json suivant, améliorer la structure du diagramme :
        1. en supprimant les liens formant des relations circulaires entre les nœuds du diagramme
        2. en vérifiant qu'au moins un nœud est lié par une relation au nœud output 
        4. en ajoutant du détail aux relations pointant vers le noeud output (tâche attendue, description, expected outpout) 
        
        JSON : {json.dumps(diagramData, indent=2)}
        
        """,
        agent=diagram_expert,
        expected_output="""Une chaîne JSON valide représentant la structure du diagramme avec :
        1. Un tableau de nœuds contenant les définitions des agents
        2. Un tableau de liens contenant les définitions des tâches/relations
        Le JSON doit conserver exactement le format initial."""
    )

    # Créer et exécuter le crew
    crew = Crew(
        agents=[diagram_expert],
        tasks=[create_diagram]
    )

    kickoff = await crew.kickoff_async()
    result = kickoff.raw
    return result.split("```json")[-1].split("```")[0].strip()


async def generate_diagram_from_description(description: str, name: str = "Nouveau Diagramme", llm: str = "openai") -> Dict:
    """
    Génère un diagramme à partir d'une description textuelle en utilisant CrewAI de manière asynchrone.
    
    Args:
        description (str): Description textuelle du diagramme à générer
        name (str): Nom du diagramme (par défaut: "Nouveau Diagramme")
        llm (str): Modèle de langage à utiliser (par défaut: "openai")
        
    Returns:
        Dict: Diagramme généré au format JSON
    """

    print(f"{MAGENTA}Starting CrewAI diagram generation with LLM: {llm}{END}")

    # Créer l'agent expert en conception de diagrammes
    diagram_expert = Agent(
        role='Expert en Conception de Diagrammes',
        goal='Créer un diagramme complet et bien structuré à partir de descriptions textuelles',
        backstory="""Vous êtes un expert dans la création de diagrammes qui représentent des workflows complexes. 
        Vous excellez dans l'identification des agents clés, leurs rôles et les relations entre eux.""",
        verbose=True,
        allow_delegation=False,
        llm=choose_llm(llm)
    )

    # Créer l'agent expert en analyse de texte
    text_analyst = Agent(
        role='Expert en Analyse de Texte',
        goal='Extraire les composants clés et les relations à partir de descriptions textuelles',
        backstory="""Vous êtes spécialisé dans l'analyse de texte pour identifier les entités importantes, 
        leurs caractéristiques et la façon dont elles interagissent entre elles.""",
        verbose=True,
        allow_delegation=False,
        llm=choose_llm(llm)
    )

    # Définir les tâches
    analyze_text = Task(
        description=f"""Analysez la description suivante et identifiez :
        1. Les agents/acteurs clés
        2. Leurs rôles et responsabilités
        3. Les relations et interactions entre eux
        
        Description : {description}
        
        Fournissez votre analyse dans un format structuré qui peut être utilisé pour créer un workflow avec CrewAI.""",
        agent=text_analyst,
        expected_output="""Une analyse structurée du texte contenant :
        1. Liste des agents identifiés avec leurs rôles
        2. Liste des tâches/relations entre les agents
        3. Toute information supplémentaire pertinente pour la création du workflow"""
    )

    create_diagram = Task(
        description=f"""À partir de l'analyse du workflow, créez une structure de diagramme avec :
        1. Des nœuds représentant les agents avec leurs propriétés
        2. Des liens représentant les tâches/relations entre les agents
        Les références circulaires sont proscrites.
        
        La sortie doit être une structure JSON valide suivant ce format :
        {{
            "name": "{name}",
            "description": "{description}",
            "nodes": [
                {{
                    "key": "identifiant_unique",
                    "type": "agent",
                    "role": "Rôle de l'Agent",
                    "goal": "Objectif de l'Agent",
                    "backstory": "Histoire de l'Agent",
                    "file":""
                }}
            ],
            "links": [
                {{
                    "id": "identifiant_unique",
                    "from": "id_noeud_source",
                    "to": "id_noeud_cible",
                    "description": "Description de la Tâche",
                    "expected_output": "Sortie Attendue",
                    "type": "task"
                }}
            ]
        }}""",
        agent=diagram_expert,
        expected_output="""Une chaîne JSON valide représentant la structure du diagramme avec :
        1. Un tableau de nœuds contenant les définitions des agents
        2. Un tableau de liens contenant les définitions des tâches/relations
        Le JSON doit suivre exactement le format spécifié."""
    )

    # Créer et exécuter le crew
    crew = Crew(
        agents=[text_analyst, diagram_expert],
        tasks=[analyze_text, create_diagram]
    )

    kickoff = await crew.kickoff_async()
    result = kickoff.raw
   

    try:
        # Extraire le JSON de la réponse
        json_str = result.split("```json")[-1].split("```")[0].strip()
        diagram_data = json.loads(json_str)
        
        # Ajouter le nœud output s'il n'existe pas déjà
        has_output = False
        for node in diagram_data["nodes"]:
            if node["key"] == "output":
                has_output = True
                break
        
        if not has_output:
            output_node = {
                "key": "output",
                "type": "output",
                "role": "Output",
                "goal": "Collecte et formate la sortie finale",
                "backstory": "Je suis responsable de collecter et de formater la sortie finale du processus",
                "file": ""
            }
            diagram_data["nodes"].append(output_node)

            # Ajouter des liens vers le nœud output pour tous les nœuds qui n'ont pas de liens sortants
            nodes_with_outgoing = set(link["from"] for link in diagram_data["links"])
            for node in diagram_data["nodes"]:
                if node["key"] != "output" and node["key"] not in nodes_with_outgoing:
                    new_link = {
                        "id": f"link_{node['key']}_output",
                        "from": node["key"],
                        "to": "output",
                        "description": "Envoie les résultats à la sortie",
                        "expected_output": "Sortie finale de cet agent",
                        "type": "task"
                    }
                    diagram_data["links"].append(new_link)
        
        # S'assurer que le nom et la description sont présents
        if "name" not in diagram_data:
            diagram_data["name"] = name
        if "description" not in diagram_data:
            diagram_data["description"] = description
        
        # Vérifier la structure et parser le résultat
        checked_json_str = await generate_diagram_check_structure(diagram_data, llm=llm)
        return json.loads(checked_json_str)

    except Exception as e:
        print(f"Erreur : {str(e)}")
        raise ValueError(f"Échec de la génération du diagramme : {str(e)}")

async def execute_process_from_diagram(data: Dict, folder: str = "", llm: str = "openai") -> Dict:
    """
    Exécute un processus basé sur un diagramme de tâches et d'agents de manière asynchrone.
    
    Args:
        data (Dict): Données JSON décrivant les nœuds et les liens du diagramme
        folder (str): Répertoire contenant les fichiers associés aux agents
        llm (str): Modèle de langage à utiliser
        
    Returns:
        Dict: Résultats de l'exécution du processus
    """
    print(f"{MAGENTA}Starting CrewAI diagram process with LLM: {llm}{END}")
    reset_chroma()

    try:
        nodes = {node['key']: node for node in data['nodes']}
        links = data['links']
        agents_dict = {}
        all_results = []
        backstories = []  # Initialize backstories list
        agent_results = {}  # Dictionnaire pour stocker les résultats par agent

        # Initialiser les agents
        for node in data['nodes']:
            summarize = node.get('summarize', "Yes")
            rag = node.get('rag', "No")
            agents_dict[node['key']] = Agent(
                role=node.get('role', ''),
                goal=node.get('goal', ''),
                backstory=node.get('backstory', ''),
                llm=choose_llm(llm),
                verbose=False
            )
            
            if file := node.get('file', ''):
                src = os.path.join(folder, file)
                if os.path.exists(src):
                    if rag=="Yes": 
                        print(f"RAG on {src}")
                        agents_dict[node['key']].tools = [choose_tool(src=src)]
                        # agents_dict[node['key']].verbose = True
                        summarize = "No"

                    if summarize=="Force":
                        print("With backstory with force")
                        backstory = await crewai_summarize(pdf=src, llm=llm)
                        agents_dict[node['key']].backstory += f"\n\nContexte du fichier {file} :\n{backstory}"
                        
                    elif summarize=="Yes":
                        print("With backstory without forcing sumup")
                        backstory = await crewai_summarize_if_not_exists(pdf=src, llm=llm)
                        agents_dict[node['key']].backstory += f"\n\nContexte du fichier {file} :\n{backstory}"

                    else:
                        print(f"No summary is used on {src}")
                        # agents_dict[node['key']].tools = [choose_tool(src=src)]
                else:
                    print(f"Le fichier {file} n'existe pas.")

        # Initialize node status
        for node in data['nodes']:
            try:
                await manager.broadcast({
                    "type": "agent_highlight",
                    "agent_id": node['key'],
                    "status": "inactive"
                })
            except Exception as e:
                print(f"Error initializing agent status: {str(e)}")

        # Construire le graphe des tâches
        task_graph = nx.DiGraph()
        for link in links:
            task_graph.add_edge(
                link['from'],
                link['to'],
                description=link.get('description', 'Effectuer une tâche'),
                expected_output=link.get('expected_output', '')
            )

        # Effectuer un tri topologique
        try:
            task_order = list(nx.topological_sort(task_graph))
        except nx.NetworkXUnfeasible:
            return {
                'status': 'error',
                'message': 'Le graphe contient des cycles, impossible de déterminer un ordre des tâches.'
            }

        roots = [node for node in task_graph.nodes if task_graph.in_degree(node) == 0]

        # Exécuter les tâches
        for node_key in task_order:
            current_node = nodes[node_key]
            outgoing_links = task_graph.out_edges(node_key, data=True)

            for from_key, to_key, link_data in outgoing_links:
                from_agent = agents_dict[from_key]
                to_agent = agents_dict[to_key]

                task = Task(
                    description=link_data['description'],
                    agent=from_agent,
                    expected_output=link_data.get('expected_output', ''),
                    tools=from_agent.tools
                )

                try:
                    # Vérifier si l'agent a déjà produit un résultat
                    if from_key in agent_results:
                        # Réutiliser le résultat existant
                        result = agent_results[from_key]
                        to_agent.backstory += f"\n\nRésultat de {from_agent.role} : {result}"
                        await manager.broadcast({
                            "type": "agent_highlight",
                            "agent_id": from_key,
                            "status": "active",
                            "task_description": f"Réutilisation du résultat de {from_agent.role}"
                        })
                        print(f"{MAGENTA}AGENT{END} : \n{RED}{from_agent.role}{END}")
                        print(f"{MAGENTA}TASK DESCRIPTION{END} : \n{GREEN}{task.description}{END}")
                        print(f"{MAGENTA}REUSING PREVIOUS RESULT FOR TASK{END} : \n{GREEN}{result}{END}")
                        await manager.broadcast({
                            "type": "agent_highlight",
                            "agent_id": from_key,
                            "status": "inactive",
                            "task_description": ""
                        })
                    else:
                        # Exécuter la tâche normalement
                        await manager.broadcast({
                            "type": "agent_highlight",
                            "agent_id": from_key,
                            "status": "active",
                            "task_description": task.description
                        })
                        crew = Crew(agents=[from_agent], tasks=[task])
                        kickoff = await crew.kickoff_async()
                        result = task.output.raw
                        print(f"{MAGENTA}TASK RESULT{END} : \n{GREEN}{result}{END}")
                        # Stocker le résultat pour cet agent
                        agent_results[from_key] = result
                        to_agent.backstory += f"\n\nRésultat de {from_agent.role} : {result}"
                        await manager.broadcast({
                            "type": "agent_highlight",
                            "agent_id": from_key,
                            "status": "inactive",
                            "task_description": ""
                        })
                        
                        formatted_result = (
                            f"\n\n***\n\n"
                            f"\n\n## {task.output.agent}\n\n"
                            f"\n\n### {task.output.description}\n\n"
                            f"\n\n{result}\n\n"
                        )
                        
                        to_agent.backstory += f"\n\nRésultat de {from_agent.role} : {result}"
                        all_results.append(formatted_result)
                        
                        print(f"{MAGENTA}AGENT{END} : \n{RED}{from_agent.role}{END}")
                        print(f"{MAGENTA}TASK DESCRIPTION{END} : \n{RED}{task.description}{END}")
                        print(f"{MAGENTA}RESULT{END} : \n\n{YELLOW}{task.output.raw}{END}")
                        
                except Exception as e:
                    print(f"Erreur lors de l'exécution de la tâche : {str(e)}")

        for agent_key, agent in agents_dict.items():
            backstories.append({
                'role': agent.role,
                'backstory': agent.backstory
            })

        return {
            'status': 'success',
            'message': "\n".join(all_results),
            'backstories': backstories,
            'branches_count': len(roots)
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }



async def ask_process_from_diagram(question: str, diagram_result: str, llm: str = "openai") -> str:
    """
    Crée un crew pour poser une question au résultat du diagramme.
    
    Args:
        question (str): La question posée par l'utilisateur
        diagram_result (str): Le résultat du diagramme à analyser
        llm (str): Le modèle de langage à utiliser
        
    Returns:
        str: La réponse à la question
    """
    try:
        # Création de l'agent d'analyse
        try:
            analyst = Agent(
                role='Analyst',
                goal='Analyser le résultat du diagramme et répondre à la question',
                backstory="""Tu es un expert en analyse de données. Tu sais interpréter des informations 
                complexes et fournir des réponses claires et précises.""",
                llm=choose_llm(llm),
                verbose=True
            )
            # print(f"{GREEN}Agent créé avec succès{END}")
        except Exception as e:
            print(f"{RED}Erreur lors de la création de l'agent: {str(e)}{END}")
            if hasattr(e, 'response'):
                print(f"{RED}Détails de l'erreur HTTP:{END}")
                print(f"{RED}Status: {e.response.status_code}{END}")
                print(f"{RED}Message: {e.response.text}{END}")
            raise

        # Tâche d'analyse
        try:
            analysis_task = Task(
                description=f"""Analyse le texte suivant et réponds à la question de l'utilisateur.
                
                résultat du diagramme: {diagram_result}
                
                Question: {question}
                
                Instructions:
                1. Lis attentivement le résultat du diagramme
                2. Identifie les informations pertinentes pour répondre à la question
                3. Fournis la réponse détaillée et claire
                4. Assure-toi que ta réponse est précise, basée sur les résultats du diagramme et tes propres connaissances sur le sujet
                """,
                expected_output="""La réponse à la demande de l'utilisateur,
                L'analyse doit inclure des explications claires.""",
                agent=analyst
            )
            #print(f"{GREEN}Tâche créée avec succès{END}")
        except Exception as e:
            print(f"{RED}Erreur lors de la création de la tâche: {str(e)}{END}")
            raise

        # Création du crew
        try:
            crew = Crew(
                agents=[analyst],
                tasks=[analysis_task]
            )
            #print(f"{GREEN}Crew créé avec succès{END}")
        except Exception as e:
            print(f"{RED}Erreur lors de la création du crew: {str(e)}{END}")
            raise

        try:
            # Exécution du processus de manière asynchrone
            kickoff = await crew.kickoff_async()
            
            result = (
                        f"\n\n***\n\n"
                        f"\n\n## {analysis_task.output.agent}\n\n"
                        f"\n\n### {analysis_task.output.description}\n\n"
                        f"\n\n{analysis_task.output.raw}\n\n"
                    )
           # print(f"RESULT : \n\n{MAGENTA}{result}{END}")
            return analysis_task.output.raw
        except Exception as e:
            error_msg = f"Error creating CrewAI Kickoff: {str(e)}"
            print(f"{RED}{error_msg}{END}")
            raise
    except Exception as e:
        error_msg = f"Error creating CrewAI Process: {str(e)}"
        print(f"{RED}{error_msg}{END}")
        return error_msg

async def enhance_diagram_from_description(diagram_data: Dict, chat_input: str, llm: str = "openai") -> Dict:
    """
    Modifie un diagramme existant en fonction d'une description textuelle.
    
    Args:
        diagram_data (Dict): Données JSON du diagramme à modifier
        chat_input (str): Description textuelle des modifications à apporter
        llm (str): Modèle de langage à utiliser
        
    Returns:
        Dict: Diagramme modifié
    """
    # Création des agents
    print(f"{MAGENTA}Starting CrewAI diagram enhancement with LLM: {llm}{END}")

    diagram_analyst = Agent(
        name="Analyste de Diagramme",
        role="Expert en analyse de diagrammes",
        goal="Comprendre la structure actuelle du diagramme sans la modifier",
        backstory="""Je suis un expert en analyse de diagrammes qui comprend parfaitement la structure des données JSON.
Je sais que le diagramme contient deux parties essentielles :
1. nodes: liste des nœuds avec les propriétés key, type, role, goal, backstory, tools, file, summarize, position
2. links: liste des liens avec les propriétés id, from, to, description, expected_output, relationship""",
        llm=choose_llm(llm),
        verbose=False
    )
    
    modification_planner = Agent(
        name="Planificateur de Modifications",
        role="Expert en planification de modifications",
        goal="Planifier les modifications tout en préservant la structure exacte du JSON",
        backstory="""Je suis un expert qui traduit des descriptions textuelles en modifications concrètes de diagramme.
Je comprends parfaitement la structure du JSON et je sais qu'il faut absolument préserver :
- Les noms exacts des propriétés (key, type, role, etc.)
- Le format des valeurs (strings, arrays, objects)
- La structure hiérarchique (nodes et links comme listes d'objets)""",
        llm=choose_llm(llm),
        verbose=True
    )
    
    diagram_modifier = Agent(
        name="Modificateur de Diagramme",
        role="Expert en modification de diagrammes",
        goal="Appliquer les modifications en conservant strictement le format JSON",
        backstory="""Je suis un expert qui modifie les diagrammes tout en maintenant leur cohérence.
Ma priorité absolue est de préserver la structure exacte du JSON :
1. Pour les nodes : key, type, role, goal, backstory, tools, file, summarize, position
2. Pour les links : id, from, to, description, expected_output, relationship""",
        llm=choose_llm(llm),
        verbose=False
    )

    # Création des tâches
    tasks = [
        Task(
            name="Analyse du Diagramme",
            agent=diagram_analyst,
            description=f"""Analyser le diagramme existant et identifier ses composants principaux.
Input JSON Structure:
{json.dumps(diagram_data, indent=2)}

Instructions :
1. Analyser la structure des nœuds (nodes) et leurs relations (links)
2. Identifier les rôles et responsabilités de chaque nœud
3. Comprendre les flux de travail existants
4. NE PAS modifier la structure ou les noms des propriétés

Format de sortie attendu : Description textuelle de l'analyse""",
            expected_output="Une description détaillée de la structure actuelle du diagramme."
        ),
        Task(
            name="Planification des Modifications",
            agent=modification_planner,
            description=f"""En te basant sur l'analyse du diagramme et la description suivante, planifie les modifications nécessaires.

Description des modifications souhaitées :
{chat_input}

Instructions :
1. Planifier les modifications nécessaires
2. S'assurer que chaque modification respecte la structure JSON
3. Vérifier que les noms des propriétés restent exacts
4. Maintenir la cohérence des relations entre les nœuds
5. S'assurer que le noeud output est bien conservé et correctement relié

Format de sortie attendu : Liste des modifications à apporter, sans inclure le JSON modifié""",
            expected_output="Une liste détaillée des modifications à apporter au diagramme."
        ),
        Task(
            name="Application des Modifications",
            agent=diagram_modifier,
            description=f"""Modifier le diagramme selon le plan établi en respectant strictement le format JSON.

Instructions :
1. Appliquer les modifications planifiées en conservant le JSON EXISTANT
2. Préserver EXACTEMENT les noms des propriétés :
   - Pour les nodes : key, type, role, goal, backstory, tools, file, summarize, position
   - Pour les links : id, from, to, description, expected_output, relationship
3. Maintenir le format des valeurs (strings, arrays, objects)
4. Conserver le noeud output et les relations qui pointent déjà vers lui
5. Retourner le JSON modifié dans un bloc de code ```json

JSON EXISTANT :
{json.dumps(diagram_data, indent=2)}

Format de sortie attendu : Le diagramme modifié au format JSON exact, encadré par ```json et ```""",
            expected_output="Le diagramme modifié au format JSON."
        )
    ]

    # Création et exécution du crew
    crew = Crew(
        agents=[diagram_analyst, modification_planner, diagram_modifier],
        tasks=tasks,
        process=Process.sequential
    )
    
    try:
        # Exécution du crew
        kickoff = crew.kickoff()
        result = kickoff.raw
        # Extraction et validation des modifications
        try:
            modified_diagram = json.loads(result.split("```json")[-1].split("```")[0].strip())
            return modified_diagram
        except json.JSONDecodeError:
            # Si le résultat n'est pas un JSON valide, retourner le diagramme original
            print(f"{RED}Erreur lors de la modification du diagramme. Retour du diagramme original.{END}")
            return diagram_data
            
    except Exception as e:
        print(f"{RED}Erreur lors de l'exécution du crew: {str(e)}{END}")
        return diagram_data