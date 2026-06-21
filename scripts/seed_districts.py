"""
Seed script: populates districts table with all districts in Andhra Pradesh and Telangana.
Run with: python -m scripts.seed_districts
"""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings

DISTRICTS = [
    # Andhra Pradesh
    {"name": "Visakhapatnam", "state": "Andhra Pradesh"},
    {"name": "East Godavari", "state": "Andhra Pradesh"},
    {"name": "West Godavari", "state": "Andhra Pradesh"},
    {"name": "Krishna", "state": "Andhra Pradesh"},
    {"name": "Guntur", "state": "Andhra Pradesh"},
    {"name": "Prakasam", "state": "Andhra Pradesh"},
    {"name": "Nellore", "state": "Andhra Pradesh"},
    {"name": "Kurnool", "state": "Andhra Pradesh"},
    {"name": "Kadapa", "state": "Andhra Pradesh"},
    {"name": "Anantapur", "state": "Andhra Pradesh"},
    {"name": "Chittoor", "state": "Andhra Pradesh"},
    {"name": "Srikakulam", "state": "Andhra Pradesh"},
    {"name": "Vizianagaram", "state": "Andhra Pradesh"},
    {"name": "Alluri Sitharama Raju", "state": "Andhra Pradesh"},
    {"name": "Anakapalli", "state": "Andhra Pradesh"},
    {"name": "Kakinada", "state": "Andhra Pradesh"},
    {"name": "Konaseema", "state": "Andhra Pradesh"},
    {"name": "Eluru", "state": "Andhra Pradesh"},
    {"name": "NTR", "state": "Andhra Pradesh"},
    {"name": "Bapatla", "state": "Andhra Pradesh"},
    {"name": "Palnadu", "state": "Andhra Pradesh"},
    {"name": "Sri Potti Sriramulu Nellore", "state": "Andhra Pradesh"},
    {"name": "Nandyal", "state": "Andhra Pradesh"},
    {"name": "Sri Sathya Sai", "state": "Andhra Pradesh"},
    {"name": "Parvathipuram Manyam", "state": "Andhra Pradesh"},
    {"name": "Tirupati", "state": "Andhra Pradesh"},

    # Telangana
    {"name": "Hyderabad", "state": "Telangana"},
    {"name": "Rangareddy", "state": "Telangana"},
    {"name": "Medchal-Malkajgiri", "state": "Telangana"},
    {"name": "Sangareddy", "state": "Telangana"},
    {"name": "Vikarabad", "state": "Telangana"},
    {"name": "Yadadri Bhuvanagiri", "state": "Telangana"},
    {"name": "Suryapet", "state": "Telangana"},
    {"name": "Nalgonda", "state": "Telangana"},
    {"name": "Mahbubnagar", "state": "Telangana"},
    {"name": "Nagarkurnool", "state": "Telangana"},
    {"name": "Wanaparthy", "state": "Telangana"},
    {"name": "Jogulamba Gadwal", "state": "Telangana"},
    {"name": "Narayanpet", "state": "Telangana"},
    {"name": "Mahabubnagar", "state": "Telangana"},
    {"name": "Khammam", "state": "Telangana"},
    {"name": "Bhadradri Kothagudem", "state": "Telangana"},
    {"name": "Mulugu", "state": "Telangana"},
    {"name": "Warangal", "state": "Telangana"},
    {"name": "Hanumakonda", "state": "Telangana"},
    {"name": "Jayashankar Bhupalpally", "state": "Telangana"},
    {"name": "Mahabubabad", "state": "Telangana"},
    {"name": "Jangaon", "state": "Telangana"},
    {"name": "Siddipet", "state": "Telangana"},
    {"name": "Medak", "state": "Telangana"},
    {"name": "Kamareddy", "state": "Telangana"},
    {"name": "Nizamabad", "state": "Telangana"},
    {"name": "Nirmal", "state": "Telangana"},
    {"name": "Adilabad", "state": "Telangana"},
    {"name": "Kumuram Bheem Asifabad", "state": "Telangana"},
    {"name": "Mancherial", "state": "Telangana"},
    {"name": "Peddapalli", "state": "Telangana"},
    {"name": "Rajanna Sircilla", "state": "Telangana"},
    {"name": "Karimnagar", "state": "Telangana"},
    {"name": "Jagtial", "state": "Telangana"},
]


async def seed():
    engine = create_async_engine(settings.databaseUrl, echo=False)
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

    from app.models.district import District
    from sqlalchemy import select

    async with SessionFactory() as session:
        for d in DISTRICTS:
            result = await session.execute(
                select(District).where(District.name == d["name"], District.state == d["state"])
            )
            existing = result.scalar_one_or_none()
            if not existing:
                session.add(District(id=uuid.uuid4(), name=d["name"], state=d["state"]))
                print(f"  + Added: {d['name']}, {d['state']}")
            else:
                print(f"  = Exists: {d['name']}, {d['state']}")

        await session.commit()
        print(f"\nSUCCESS: Seed complete. {len(DISTRICTS)} districts processed.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
