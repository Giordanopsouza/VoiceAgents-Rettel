from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AppointmentSlot(Base):
    __tablename__ = "appointment_slot"
    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'occupied')",
            name="ck_appointment_slot_status",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    dentist_name: Mapped[str] = mapped_column(String, nullable=False)
    starts_at: Mapped[str] = mapped_column(String, nullable=False)
    ends_at: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="slot")


class Appointment(Base):
    __tablename__ = "appointment"
    __table_args__ = (
        CheckConstraint("status = 'active'", name="ck_appointment_status"),
        Index(
            "uq_appointment_one_active_per_slot",
            "slot_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    slot_id: Mapped[str] = mapped_column(
        ForeignKey("appointment_slot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    patient_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    slot: Mapped[AppointmentSlot] = relationship(back_populates="appointments")
    idempotency_record: Mapped["IdempotencyRecord | None"] = relationship(
        back_populates="appointment"
    )
    request_events: Mapped[list["RequestEvent"]] = relationship(
        back_populates="appointment"
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_record"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    appointment_id: Mapped[str] = mapped_column(
        ForeignKey("appointment.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    appointment: Mapped[Appointment] = relationship(back_populates="idempotency_record")


class RequestEvent(Base):
    __tablename__ = "request_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    appointment_id: Mapped[str | None] = mapped_column(
        ForeignKey("appointment.id"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    call_id: Mapped[str | None] = mapped_column(String, nullable=True)

    appointment: Mapped[Appointment | None] = relationship(
        back_populates="request_events"
    )
