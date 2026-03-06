def _get_dummy_ocds_response() -> dict[str, Any]:
    ocid = f"ocds-{uuid.uuid4().hex[:8]}"
    id = f"award-{uuid.uuid4().hex[:8]}"
    description = _generate_description()
    return {
        "uri": "https://example.local/ocds/releases",
        "version": "1.1",
        "publisher": {
            "name": "OCDS Dummy Publisher",
            "uri": "https://www.tenders.gov.au",
        },
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "publishedDate": "2026-03-02T00:00:00Z",
        "releases": [
            {
                "ocid": ocid,
                "id": "release-0001",
                "date": "2026-03-02T00:00:00Z",
                "tag": ["award"],
                "initiationType": "tender",
                "awards": [
                    {
                        "id": id,
                        "title": "Dummy Cloud Migration Services",
                        "description": description,
                        "status": "active",
                        "date": "2026-03-02T00:00:00Z",
                        "value": {
                            "amount": 250000.0,
                            "currency": "AUD",
                        },
                        "suppliers": [
                            {
                                "name": "Dummy Supplier Pty Ltd",
                            }
                        ],
                    }
                ],
            }
        ],
    }



def _generate_description() -> str:
    prompts = [
        "Generate a fictitious government contract description for something related to defence.",
        "Generate a fictitious government contract description for something related to healthcare.",
        "Generate a fictitious government contract description for something related to infrastructure.",
        "Generate a fictitious government contract description for something related to justice.",
        "Generate a fictitious government contract description for something related to immigration."
    ]
    modifiers = [
        "Focus on emerging technologies.",
        "Make it a small-scale regional project.",
        "Include a focus on sustainability.",
        "Set the timeline for 10 years.",
        "Emphasize cybersecurity requirements."
    ]    
    endpoint = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", "").strip().rstrip("/")
    project_name = os.getenv("AZURE_AI_FOUNDRY_PROJECT", "").strip()
    configured_agent_id = "asst_N5IUF0XWUCRksPX64PlpfzKf"

    project_endpoint = "https://sra1d-foundry-01.services.ai.azure.com/api/projects/proj-default"
    if endpoint and project_name:
        project_endpoint = f"{endpoint}/api/projects/{project_name}"

    client = AIProjectClient(
        credential=DefaultAzureCredential(),
        endpoint=project_endpoint,
    )

    agent_id = configured_agent_id or "asst_NXAoRTS8nqCoUZTQrM6gP06T"
    agent = client.agents.get_agent(agent_id)
    thread = client.agents.threads.create()

    client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=random.choice(prompts) + " " + random.choice(modifiers),
    )

    run = client.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent.id,
    )

    if run.status == "failed":
        return "Error generating description: Agent run failed."

    messages = client.agents.messages.list(
        thread_id=thread.id,
        order=ListSortOrder.DESCENDING,
    )
    if not messages:
        return "Error generating description: Agent returned no messages."

    latest = next(iter(messages), None)
    if latest is None:
        return "Error generating description: Agent returned no messages."
    content = latest.content    
    return content if isinstance(content, str) else str(content)

