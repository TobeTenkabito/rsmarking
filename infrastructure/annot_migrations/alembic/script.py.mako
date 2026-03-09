"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
<<<<<<< HEAD
import geoalchemy2
=======
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
<<<<<<< HEAD
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
=======
down_revision: Union[str, None] = ${repr(down_revision)}
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
<<<<<<< HEAD
    """Upgrade schema."""
=======
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
<<<<<<< HEAD
    """Downgrade schema."""
=======
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
    ${downgrades if downgrades else "pass"}
