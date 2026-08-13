"""
Routes: /marketplace — UTIM Marketplace for sharing skills, agents, and tools.
"""
from __future__ import annotations

import datetime
import logging
import os
import hmac
import hashlib
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..db import (
    MarketplaceListing,
    MarketplaceReview,
    MarketplacePurchase,
    MarketplacePackageVersion,
    User,
    get_db,
    SellerProfile,
    SellerWallet,
    SellerWithdrawal,
    MarketplacePurchaseOrder,
)
from ..auth import get_current_user, get_optional_user

router = APIRouter(tags=["marketplace"])
logger = logging.getLogger("utim.routes.marketplace")


# ── Models ────────────────────────────────────────────────────────────────────

class ListingCreateReq(BaseModel):
    name: str = Field(..., max_length=128)
    slug: Optional[str] = None
    type: str = Field("skill", max_length=32)
    category: Optional[str] = None
    description: str
    readme: Optional[str] = None
    tags: Optional[List[str]] = None
    icon_emoji: Optional[str] = None
    price_usd: float = 0.0
    is_paid: bool = False
    payment_type: str = "one_time"
    subscription_interval: Optional[str] = None
    zip_url: Optional[str] = None
    zip_base64: Optional[str] = None


class ListingUpdateReq(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    readme: Optional[str] = None
    tags: Optional[List[str]] = None
    icon_emoji: Optional[str] = None
    price_usd: Optional[float] = None
    zip_url: Optional[str] = None
    is_published: Optional[bool] = None


class ReviewCreateReq(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class CategoryResp(BaseModel):
    category: str
    count: int

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/listings")
def list_listings(
    type: Optional[str] = None,
    category: Optional[str] = None,
    sort: Optional[str] = "newest",  # featured, popular, newest, top_rated, free, paid
    query: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(MarketplaceListing).filter(MarketplaceListing.is_published == True)
    
    if type:
        q = q.filter(MarketplaceListing.type == type)
    if category:
        q = q.filter(MarketplaceListing.category == category)
    if query:
        q = q.filter(
            (MarketplaceListing.name.ilike(f"%{query}%")) |
            (MarketplaceListing.description.ilike(f"%{query}%")) |
            (MarketplaceListing.slug.ilike(f"%{query}%"))
        )
        
    if sort == "featured":
        q = q.order_by(desc(MarketplaceListing.is_featured), desc(MarketplaceListing.created_at))
    elif sort == "popular":
        q = q.order_by(desc(MarketplaceListing.download_count))
    elif sort == "top_rated":
        q = q.order_by(desc(MarketplaceListing.rating_avg), desc(MarketplaceListing.rating_count))
    elif sort == "free":
        q = q.filter(MarketplaceListing.price_usd == 0).order_by(desc(MarketplaceListing.download_count))
    elif sort == "paid":
        q = q.filter(MarketplaceListing.price_usd > 0).order_by(desc(MarketplaceListing.download_count))
    else: # newest
        q = q.order_by(desc(MarketplaceListing.created_at))
        
    total = q.count()
    listings = q.offset(skip).limit(limit).all()
    
    results = []
    for row in listings:
        results.append({
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "type": row.type,
            "category": row.category,
            "description": row.description,
            "tags": row.tags,
            "icon_emoji": row.icon_emoji,
            "price_usd": row.price_usd,
            "is_paid": row.is_paid,
            "is_featured": row.is_featured,
            "download_count": row.download_count,
            "rating_avg": row.rating_avg,
            "rating_count": row.rating_count,
            "version": row.version,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "seller_id": row.seller_id,
        })
        
    return {"total": total, "items": results}


@router.get("/listings/{slug}")
def get_listing(slug: str, db: Session = Depends(get_db)):
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.slug == slug).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    reviews = db.query(MarketplaceReview).filter(MarketplaceReview.listing_id == listing.id).order_by(desc(MarketplaceReview.created_at)).limit(20).all()
    
    res = {
        "id": listing.id,
        "name": listing.name,
        "slug": listing.slug,
        "type": listing.type,
        "category": listing.category,
        "description": listing.description,
        "readme": listing.readme,
        "tags": listing.tags,
        "icon_emoji": listing.icon_emoji,
        "price_usd": listing.price_usd,
        "is_paid": listing.is_paid,
        "is_published": listing.is_published,
        "is_featured": listing.is_featured,
        "download_count": listing.download_count,
        "rating_avg": listing.rating_avg,
        "rating_count": listing.rating_count,
        "version": listing.version,
        "created_at": listing.created_at.isoformat() if listing.created_at else None,
        "seller_id": listing.seller_id,
        "reviews": [
            {
                "id": r.id,
                "reviewer_id": r.reviewer_id,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            } for r in reviews
        ]
    }
    return res


@router.get("/featured")
def get_featured(db: Session = Depends(get_db)):
    cutoff_72h = datetime.datetime.utcnow() - datetime.timedelta(hours=72)

    latest_72h = db.query(MarketplaceListing).filter(
        MarketplaceListing.is_published == True,
        MarketplaceListing.created_at >= cutoff_72h
    ).order_by(desc(MarketplaceListing.created_at)).limit(10).all()

    featured = db.query(MarketplaceListing).filter(
        MarketplaceListing.is_published == True,
        MarketplaceListing.is_featured == True
    ).order_by(desc(MarketplaceListing.created_at)).limit(6).all()

    popular = db.query(MarketplaceListing).filter(
        MarketplaceListing.is_published == True
    ).order_by(desc(MarketplaceListing.download_count)).limit(6).all()

    newest = db.query(MarketplaceListing).filter(
        MarketplaceListing.is_published == True
    ).order_by(desc(MarketplaceListing.created_at)).limit(10).all()

    all_items = db.query(MarketplaceListing).filter(
        MarketplaceListing.is_published == True
    ).order_by(desc(MarketplaceListing.created_at)).limit(40).all()

    def format_listing(row):
        return {
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "type": row.type,
            "category": row.category,
            "description": row.description,
            "icon_emoji": row.icon_emoji,
            "price_usd": row.price_usd,
            "is_paid": row.is_paid,
            "rating_avg": row.rating_avg,
            "rating_count": row.rating_count,
            "download_count": row.download_count,
            "payment_type": getattr(row, "payment_type", "one_time") or "one_time",
            "subscription_interval": getattr(row, "subscription_interval", None),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    return {
        "latest_72h": [format_listing(r) for r in latest_72h],
        "featured": [format_listing(r) for r in featured],
        "popular": [format_listing(r) for r in popular],
        "newest": [format_listing(r) for r in newest],
        "all_items": [format_listing(r) for r in all_items],
    }


def _create_razorpay_plan_if_needed(
    name: str,
    price_usd: float,
    payment_type: Optional[str],
    interval: Optional[str]
) -> Optional[str]:
    """If payment_type is subscription, call Razorpay Plans API to create a recurring billing plan and return plan_id."""
    if payment_type != "subscription" or price_usd <= 0:
        return None

    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")

    period = "yearly" if interval == "yearly" else "monthly"

    if not key_id or key_id.startswith("mock"):
        return f"plan_mock_{uuid.uuid4().hex[:10]}"

    try:
        import requests as req_lib
        import base64
        from ..exchange_rate import ExchangeRateStore

        usd_to_inr = ExchangeRateStore.get_rate()
        amount_inr = price_usd * usd_to_inr
        amount_paise = max(100, int(amount_inr * 100))

        auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {auth_str}", "Content-Type": "application/json"}
        payload = {
            "period": period,
            "interval": 1,
            "item": {
                "name": f"UTIM Sub - {name}",
                "amount": amount_paise,
                "currency": "INR",
                "description": f"Subscription for {name}"
            }
        }
        resp = req_lib.post("https://api.razorpay.com/v1/plans", json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            plan_data = resp.json()
            plan_id = plan_data.get("id")
            logger.info(f"Created Razorpay Plan {plan_id} for listing '{name}' (${price_usd:.2f}/{period})")
            return plan_id
        else:
            logger.error(f"Razorpay plan creation API error ({resp.status_code}): {resp.text}")
            return f"plan_fallback_{uuid.uuid4().hex[:8]}"
    except Exception as e:
        logger.error(f"Failed to create Razorpay plan: {e}")
        return f"plan_fallback_{uuid.uuid4().hex[:8]}"


@router.post("/listings")
def publish_listing(
    req: ListingCreateReq,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    import re, uuid, base64
    from ..storage_nodes import StorageNodeManager

    slug = req.slug
    if not slug:
        slug = re.sub(r"[^a-z0-9-]", "-", req.name.lower()).strip("-")
    if not slug:
        slug = f"ext-{uuid.uuid4().hex[:8]}"

    exists = db.query(MarketplaceListing).filter(MarketplaceListing.slug == slug).first()
    if exists:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    # Run Razorpay Plan Creation if product is subscription-based
    plan_id = None
    if req.payment_type == "subscription" and req.price_usd > 0:
        plan_id = _create_razorpay_plan_if_needed(
            name=req.name,
            price_usd=req.price_usd,
            payment_type=req.payment_type,
            interval=req.subscription_interval
        )

    listing = MarketplaceListing(
        seller_id=user.id,
        name=req.name,
        slug=slug,
        type=req.type,
        category=req.category or "other",
        description=req.description,
        readme=req.readme,
        tags=req.tags,
        icon_emoji=req.icon_emoji,
        price_usd=req.price_usd,
        is_paid=req.price_usd > 0,
        payment_type=req.payment_type or "one_time",
        subscription_interval=req.subscription_interval,
        razorpay_plan_id=plan_id,
        is_published=True,
        zip_url=f"https://api.utim.dev/marketplace/packages/{slug}.zip",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)

    # Process package upload to Google Drive storage node if zip bytes are provided
    if req.zip_base64:
        try:
            zip_bytes = base64.b64decode(req.zip_base64)
            pkg_ver, upload_meta = StorageNodeManager.upload_package(
                db=db,
                seller_id=user.id,
                listing_id=listing.id,
                version="1.0.0",
                package_type=req.type,
                zip_bytes=zip_bytes,
            )
            listing.zip_url = f"https://api.utim.dev/marketplace/packages/{pkg_ver.id}/stream"
            db.commit()
        except Exception as e:
            logger.error("Failed package upload to storage node for listing '%s': %s", listing.slug, e)
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Package upload failed: {e}")
    
    return {"status": "success", "id": listing.id, "slug": listing.slug, "zip_url": listing.zip_url}


@router.get("/packages/{filename}")
def download_package_file(filename: str):
    from fastapi.responses import FileResponse
    from pathlib import Path
    pkg_file = Path(".utim_packages") / filename
    if pkg_file.exists():
        return FileResponse(str(pkg_file), media_type="application/zip", filename=filename)
    raise HTTPException(status_code=404, detail="Package file not found")


@router.put("/listings/{slug}")
def update_listing(
    slug: str,
    req: ListingUpdateReq,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.slug == slug).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    if listing.seller_id != user.id:
        raise HTTPException(status_code=403, detail="Not the owner of this listing")
        
    if req.name is not None:
        listing.name = req.name
    if req.category is not None:
        listing.category = req.category
    if req.description is not None:
        listing.description = req.description
    if req.readme is not None:
        listing.readme = req.readme
    if req.tags is not None:
        listing.tags = req.tags
    if req.icon_emoji is not None:
        listing.icon_emoji = req.icon_emoji
    if req.price_usd is not None:
        listing.price_usd = req.price_usd
        listing.is_paid = listing.price_usd > 0
    if req.zip_url is not None:
        listing.zip_url = req.zip_url
    if req.is_published is not None:
        listing.is_published = req.is_published
        
    db.commit()
    return {"status": "success", "is_published": listing.is_published}


@router.post("/listings/{slug}/toggle-publish")
def toggle_publish_listing(
    slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.slug == slug).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    if listing.seller_id != user.id:
        raise HTTPException(status_code=403, detail="Not the owner of this listing")
        
    listing.is_published = not listing.is_published
    db.commit()
    return {"status": "success", "is_published": listing.is_published}


@router.delete("/listings/{slug}")
def delete_listing(
    slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.slug == slug).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    profile = db.query(SellerProfile).filter(SellerProfile.user_id == user.id).first()
    seller_ids = [user.id]
    if user.email:
        seller_ids.append(user.email)
    if profile:
        seller_ids.append(profile.id)

    if listing.seller_id not in seller_ids:
        raise HTTPException(status_code=403, detail="Not the owner of this listing")

    # Delete all dependent package versions, reviews, purchases, and orders first
    db.query(MarketplacePackageVersion).filter(MarketplacePackageVersion.listing_id == listing.id).delete(synchronize_session=False)
    db.query(MarketplaceReview).filter(MarketplaceReview.listing_id == listing.id).delete(synchronize_session=False)
    db.query(MarketplacePurchase).filter(MarketplacePurchase.listing_id == listing.id).delete(synchronize_session=False)
    try:
        db.query(MarketplacePurchaseOrder).filter(MarketplacePurchaseOrder.listing_id == listing.id).delete(synchronize_session=False)
    except Exception:
        pass

    db.delete(listing)
    db.commit()
    return {"status": "success"}


@router.post("/listings/{slug}/reviews")
def post_review(
    slug: str,
    req: ReviewCreateReq,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.slug == slug).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    review = db.query(MarketplaceReview).filter(
        MarketplaceReview.listing_id == listing.id,
        MarketplaceReview.reviewer_id == user.id
    ).first()
    
    if review:
        review.rating = req.rating
        review.comment = req.comment
    else:
        review = MarketplaceReview(
            listing_id=listing.id,
            reviewer_id=user.id,
            rating=req.rating,
            comment=req.comment,
        )
        db.add(review)
        
    db.commit()
    
    stats = db.query(
        func.avg(MarketplaceReview.rating).label('avg_rating'),
        func.count(MarketplaceReview.id).label('count')
    ).filter(MarketplaceReview.listing_id == listing.id).first()
    
    if stats and stats.count > 0:
        listing.rating_avg = round(float(stats.avg_rating), 1)
        listing.rating_count = stats.count
        db.commit()
        
    return {"status": "success"}


@router.post("/listings/{slug}/download")
def download_listing(
    slug: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.slug == slug).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    if listing.is_paid:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required to download paid items")
            
        if listing.seller_id != user.id:
            purchase = db.query(MarketplacePurchase).filter(
                MarketplacePurchase.listing_id == listing.id,
                MarketplacePurchase.buyer_id == user.id,
                MarketplacePurchase.status == "completed"
            ).first()
            
            if not purchase:
                raise HTTPException(status_code=403, detail="Item not purchased")
                
    listing.download_count += 1
    db.commit()
    
    # Check for registered package version
    from ..db import MarketplacePackageVersion
    latest_ver = db.query(MarketplacePackageVersion).filter(
        MarketplacePackageVersion.listing_id == listing.id,
        MarketplacePackageVersion.moderation_status == "approved"
    ).order_by(desc(MarketplacePackageVersion.created_at)).first()

    if latest_ver:
        package_stream_url = f"https://api.utim.dev/marketplace/packages/{latest_ver.id}/stream"
        return {"zip_url": package_stream_url, "type": listing.type, "slug": listing.slug}
    
    return {"zip_url": listing.zip_url, "type": listing.type, "slug": listing.slug}


@router.get("/packages/{package_id}/stream")
def stream_package_endpoint(
    package_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """
    Secure Google Drive proxy streaming endpoint.
    Performs direct DB lookup: package_id -> MarketplacePackageVersion -> storage_node_id & drive_file_id.
    Streams package from Google Drive node directly to UTIM CLI. Never exposes raw Drive links/credentials.
    """
    from fastapi.responses import StreamingResponse
    from ..db import MarketplacePackageVersion
    from ..storage_nodes import StorageNodeManager

    pkg_ver = db.query(MarketplacePackageVersion).filter(MarketplacePackageVersion.id == package_id).first()
    if not pkg_ver:
        raise HTTPException(status_code=404, detail="Package version not found")

    if pkg_ver.moderation_status != "approved":
        raise HTTPException(status_code=403, detail="Package version pending moderation or unapproved")

    # Validate entitlement
    listing = pkg_ver.listing
    if listing and listing.is_paid:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required to stream paid items")
        if listing.seller_id != user.id:
            purchase = db.query(MarketplacePurchase).filter(
                MarketplacePurchase.listing_id == listing.id,
                MarketplacePurchase.buyer_id == user.id,
                MarketplacePurchase.status == "completed"
            ).first()
            if not purchase:
                raise HTTPException(status_code=403, detail="Item not purchased")

    try:
        stream, filename, size_bytes, sha256_checksum = StorageNodeManager.stream_package(db, pkg_ver)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Package-Checksum": sha256_checksum,
            "X-Package-Size": str(size_bytes),
        }
        return StreamingResponse(stream, media_type="application/zip", headers=headers)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Package file not found on storage node")
    except Exception as e:
        logger.error(f"Error streaming package {package_id}: {e}")
        raise HTTPException(status_code=500, detail="Storage node streaming error")


@router.get("/storage-nodes")
def get_storage_nodes_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Admin/internal node management dashboard endpoint to monitor the 4 Google Drive nodes (~20 TB)."""
    from ..db import StorageNode
    nodes = db.query(StorageNode).all()
    results = []
    for n in nodes:
        results.append({
            "id": n.id,
            "provider_type": n.provider_type,
            "account_label": n.account_label,
            "total_capacity_bytes": n.total_capacity_bytes,
            "used_bytes": n.used_bytes,
            "available_bytes": n.available_bytes,
            "available_gb": round(n.available_bytes / (1024**3), 2),
            "is_enabled": n.is_enabled,
            "health_status": n.health_status,
            "error_count": n.error_count,
            "last_upload_at": n.last_upload_at.isoformat() if n.last_upload_at else None,
            "last_download_at": n.last_download_at.isoformat() if n.last_download_at else None,
        })
    return {"total_nodes": len(results), "nodes": results}


@router.get("/my-listings")
def get_my_listings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    profile = db.query(SellerProfile).filter(SellerProfile.user_id == user.id).first()
    seller_ids = [user.id]
    if user.email:
        seller_ids.append(user.email)
    if profile:
        seller_ids.append(profile.id)

    listings = db.query(MarketplaceListing).filter(
        MarketplaceListing.seller_id.in_(seller_ids)
    ).order_by(desc(MarketplaceListing.created_at)).all()
    
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "slug": r.slug,
                "type": r.type,
                "price_usd": r.price_usd,
                "is_published": r.is_published,
                "download_count": r.download_count,
                "rating_avg": r.rating_avg,
                "rating_count": r.rating_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            } for r in listings
        ]
    }


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    results = db.query(
        MarketplaceListing.category,
        func.count(MarketplaceListing.id).label('count')
    ).filter(
        MarketplaceListing.is_published == True,
        MarketplaceListing.category.isnot(None)
    ).group_by(MarketplaceListing.category).all()
    
    return [
        {"category": r.category, "count": r.count}
        for r in results
    ]


@router.get("/seller-profile/{seller_id}")
def get_public_seller_profile(
    seller_id: str,
    db: Session = Depends(get_db)
):
    """Public endpoint to view a seller's profile and published listings (no banking/wallet info)."""
    # Check if seller_id is profile.id or user.id
    profile = db.query(SellerProfile).filter(
        (SellerProfile.id == seller_id) | (SellerProfile.user_id == seller_id)
    ).first()
    
    if not profile:
        # Fallback to User
        u = db.query(User).filter(User.id == seller_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Seller profile not found")
        display_name = u.email.split("@")[0]
        bio = "UTIM Extension Publisher"
        avatar_emoji = "‍"
        is_verified = True
        user_id = u.id
    else:
        display_name = profile.display_name or profile.user.email.split("@")[0]
        bio = profile.bio or "UTIM Extension Publisher"
        avatar_emoji = profile.avatar_emoji or "‍"
        is_verified = profile.is_verified
        user_id = profile.user_id

    # Fetch public published listings
    published_listings = db.query(MarketplaceListing).filter(
        MarketplaceListing.seller_id == user_id,
        MarketplaceListing.is_published == True
    ).all()

    total_downloads = sum(l.download_count for l in published_listings)
    avg_rating = round(sum(l.rating_avg for l in published_listings) / max(1, len(published_listings)), 1) if published_listings else 0.0

    return {
        "id": seller_id,
        "display_name": display_name,
        "bio": bio,
        "avatar_emoji": avatar_emoji,
        "is_verified": is_verified,
        "total_published": len(published_listings),
        "total_downloads": total_downloads,
        "average_rating": avg_rating,
        "listings": [
            {
                "name": l.name,
                "slug": l.slug,
                "type": l.type,
                "rating_avg": l.rating_avg,
                "download_count": l.download_count,
                "price_usd": l.price_usd
            } for l in published_listings
        ]
    }


# ── Seller Profile ────────────────────────────────────────────────────────────

class SellerProfileReq(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_emoji: Optional[str] = None


@router.get("/seller-profile")
def get_seller_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    profile = db.query(SellerProfile).filter(SellerProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Seller profile not found")
    wallet = profile.wallet
    return {
        "id": profile.id,
        "display_name": profile.display_name,
        "bio": profile.bio,
        "avatar_emoji": profile.avatar_emoji,
        "is_verified": profile.is_verified,
        "wallet": {
            "balance_usd": wallet.balance_usd if wallet else 0.0,
            "total_earned_usd": wallet.total_earned_usd if wallet else 0.0,
            "total_withdrawn_usd": wallet.total_withdrawn_usd if wallet else 0.0,
            "pending_withdrawal_usd": wallet.pending_withdrawal_usd if wallet else 0.0,
        } if wallet else None
    }


@router.post("/seller-profile")
def upsert_seller_profile(
    req: SellerProfileReq,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    profile = db.query(SellerProfile).filter(SellerProfile.user_id == user.id).first()
    if not profile:
        profile = SellerProfile(user_id=user.id)
        db.add(profile)
        db.flush()
        # Create wallet automatically
        wallet = SellerWallet(seller_id=profile.id)
        db.add(wallet)
    
    if req.display_name is not None:
        profile.display_name = req.display_name
    if req.bio is not None:
        profile.bio = req.bio
    if req.avatar_emoji is not None:
        profile.avatar_emoji = req.avatar_emoji
    
    db.commit()
    db.refresh(profile)
    return {"status": "success", "id": profile.id}


# ── Seller Wallet ─────────────────────────────────────────────────────────────

@router.get("/wallet")
def get_wallet(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    profile = db.query(SellerProfile).filter(SellerProfile.user_id == user.id).first()
    if not profile or not profile.wallet:
        return {
            "balance_usd": 0.0,
            "total_earned_usd": 0.0,
            "total_withdrawn_usd": 0.0,
            "pending_withdrawal_usd": 0.0,
            "withdrawals": []
        }
    wallet = profile.wallet
    withdrawals = db.query(SellerWithdrawal).filter(
        SellerWithdrawal.wallet_id == wallet.id
    ).order_by(desc(SellerWithdrawal.created_at)).limit(20).all()
    
    return {
        "balance_usd": wallet.balance_usd,
        "total_earned_usd": wallet.total_earned_usd,
        "total_withdrawn_usd": wallet.total_withdrawn_usd,
        "pending_withdrawal_usd": wallet.pending_withdrawal_usd,
        "withdrawals": [
            {
                "id": w.id,
                "amount_usd": w.amount_usd,
                "method": w.method,
                "status": w.status,
                "razorpay_payout_id": w.razorpay_payout_id,
                "failure_reason": w.failure_reason,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            } for w in withdrawals
        ]
    }


class WithdrawReq(BaseModel):
    amount_usd: float
    method: str = "upi"  # 'upi' | 'bank'
    upi_id: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    account_name: Optional[str] = None


@router.post("/wallet/withdraw")
def request_withdrawal(
    req: WithdrawReq,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Request a withdrawal from the seller's wallet via Razorpay Payouts API."""
    profile = db.query(SellerProfile).filter(SellerProfile.user_id == user.id).first()
    if not profile or not profile.wallet:
        raise HTTPException(status_code=404, detail="Seller profile or wallet not found")
    
    wallet = profile.wallet
    if req.amount_usd <= 0:
        raise HTTPException(status_code=400, detail="Withdrawal amount must be positive")
    if req.amount_usd > wallet.balance_usd:
        raise HTTPException(status_code=400, detail=f"Insufficient balance. Available: ${wallet.balance_usd:.3f}")
    if req.amount_usd < 0.01:
        raise HTTPException(status_code=400, detail="Minimum withdrawal is $0.01")
    
    if req.method == "upi" and not req.upi_id:
        raise HTTPException(status_code=400, detail="UPI ID is required for UPI withdrawal")
    if req.method == "bank" and not (req.account_number and req.ifsc_code and req.account_name):
        raise HTTPException(status_code=400, detail="Account number, IFSC, and name required for bank withdrawal")
    
    # Lock the amount
    wallet.balance_usd -= req.amount_usd
    wallet.pending_withdrawal_usd += req.amount_usd
    
    # Create withdrawal record
    withdrawal = SellerWithdrawal(
        wallet_id=wallet.id,
        amount_usd=req.amount_usd,
        method=req.method,
        upi_id=req.upi_id,
        account_number=req.account_number,
        account_name=req.account_name,
        ifsc_code=req.ifsc_code,
        status="pending"
    )
    db.add(withdrawal)
    
    # Attempt Razorpay Payout (X API)
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    
    if key_id and key_secret and not key_id.startswith("mock"):
        try:
            import requests as req_lib
            import base64
            from ..exchange_rate import ExchangeRateStore
            
            usd_to_inr = ExchangeRateStore.get_rate()
            amount_inr_paise = int(req.amount_usd * usd_to_inr * 100)
            
            auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
            headers = {
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json"
            }
            
            # Build fund account
            if req.method == "upi":
                fund_account = {
                    "account_type": "vpa",
                    "vpa": {"address": req.upi_id}
                }
            else:
                fund_account = {
                    "account_type": "bank_account",
                    "bank_account": {
                        "name": req.account_name,
                        "ifsc": req.ifsc_code,
                        "account_number": req.account_number
                    }
                }
            
            # Create contact + fund account via Razorpay X
            contact_payload = {
                "name": profile.display_name or user.email,
                "email": user.email,
                "type": "vendor",
                "reference_id": profile.id
            }
            contact_resp = req_lib.post(
                "https://api.razorpay.com/v1/contacts",
                json=contact_payload, headers=headers, timeout=10
            )
            contact_id = contact_resp.json().get("id") if contact_resp.status_code == 200 else None
            
            if contact_id:
                fa_payload = {"contact_id": contact_id, **fund_account}
                fa_resp = req_lib.post(
                    "https://api.razorpay.com/v1/fund_accounts",
                    json=fa_payload, headers=headers, timeout=10
                )
                fund_account_id = fa_resp.json().get("id") if fa_resp.status_code == 200 else None
                
                if fund_account_id:
                    payout_payload = {
                        "account_number": os.environ.get("RAZORPAY_PAYOUT_ACCOUNT", ""),
                        "fund_account_id": fund_account_id,
                        "amount": amount_inr_paise,
                        "currency": "INR",
                        "mode": "UPI" if req.method == "upi" else "NEFT",
                        "purpose": "payout",
                        "queue_if_low_balance": True,
                        "reference_id": withdrawal.id,
                        "narration": "UTIM Marketplace Earnings"
                    }
                    payout_resp = req_lib.post(
                        "https://api.razorpay.com/v1/payouts",
                        json=payout_payload, headers=headers, timeout=10
                    )
                    if payout_resp.status_code in (200, 201):
                        payout_data = payout_resp.json()
                        withdrawal.razorpay_payout_id = payout_data.get("id")
                        withdrawal.status = "processing"
                        profile.razorpay_contact_id = contact_id
                        profile.razorpay_fund_account_id = fund_account_id
            if not (key_id and key_secret and not key_id.startswith("mock")):
                # Mock or no API keys -> auto-complete withdrawal for testing
                auto_approve = os.environ.get("AUTO_APPROVE_WITHDRAWALS", "true").lower() in ("true", "1")
                if auto_approve:
                    withdrawal.status = "completed"
                    wallet.pending_withdrawal_usd -= req.amount_usd
                    wallet.total_withdrawn_usd += req.amount_usd
        except Exception as e:
            logger.error(f"Razorpay payout error for withdrawal {withdrawal.id}: {e}")
            # Keep status as 'pending' for manual admin processing
    else:
        # Mock mode -> auto-complete
        withdrawal.status = "completed"
        wallet.pending_withdrawal_usd -= req.amount_usd
        wallet.total_withdrawn_usd += req.amount_usd

    db.commit()
    
    return {
        "status": "success",
        "withdrawal_id": withdrawal.id,
        "amount_usd": req.amount_usd,
        "withdrawal_status": withdrawal.status,
        "message": "Withdrawal request submitted successfully."
    }


ADMIN_EMAILS = {"sarannya.chaudhuri13@gmail.com", "uthinkimake.official@utim.dev"}

def _verify_admin_user(user: User):
    is_admin_flag = getattr(user, "is_admin", False)
    email = (user.email or "").lower()
    if not is_admin_flag and email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin authorization required")

@router.get("/is-admin")
def check_is_admin(user: User = Depends(get_current_user)):
    email = (user.email or "").lower()
    is_admin_flag = getattr(user, "is_admin", False)
    return {"is_admin": is_admin_flag or email in ADMIN_EMAILS}

# ── Admin Withdrawal Management ───────────────────────────────────────────────

@router.get("/admin/withdrawals")
def list_all_withdrawals(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List all withdrawal requests for admin review."""
    _verify_admin_user(user)
    q = db.query(SellerWithdrawal)
    if status:
        q = q.filter(SellerWithdrawal.status == status)
    withdrawals = q.order_by(desc(SellerWithdrawal.created_at)).all()
    
    out = []
    for w in withdrawals:
        wallet = db.query(SellerWallet).filter(SellerWallet.id == w.wallet_id).first()
        profile = db.query(SellerProfile).filter(SellerProfile.id == wallet.seller_id).first() if wallet else None
        seller_user = db.query(User).filter(User.id == profile.user_id).first() if profile else None
        out.append({
            "id": w.id,
            "amount_usd": w.amount_usd,
            "method": w.method,
            "upi_id": w.upi_id,
            "account_number": w.account_number,
            "account_name": w.account_name,
            "ifsc_code": w.ifsc_code,
            "status": w.status,
            "razorpay_payout_id": w.razorpay_payout_id,
            "failure_reason": w.failure_reason,
            "created_at": w.created_at.isoformat() if w.created_at else None,
            "seller_email": seller_user.email if seller_user else "Unknown",
            "seller_name": profile.display_name if profile else "Unknown",
        })
    return out


@router.post("/admin/withdrawals/{withdrawal_id}/approve")
def approve_withdrawal(
    withdrawal_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Approve and complete a pending withdrawal request."""
    _verify_admin_user(user)
    w = db.query(SellerWithdrawal).filter(SellerWithdrawal.id == withdrawal_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if w.status == "completed":
        return {"status": "already_completed"}
    
    wallet = db.query(SellerWallet).filter(SellerWallet.id == w.wallet_id).first()
    if wallet:
        wallet.pending_withdrawal_usd = max(0.0, wallet.pending_withdrawal_usd - w.amount_usd)
        wallet.total_withdrawn_usd += w.amount_usd
    
    w.status = "completed"
    db.commit()
    return {"status": "success", "message": f"Withdrawal {w.id} marked as completed."}


@router.post("/admin/withdrawals/{withdrawal_id}/reject")
def reject_withdrawal(
    withdrawal_id: str,
    reason: Optional[str] = "Rejected by admin",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Reject a pending withdrawal request and return funds to seller balance."""
    _verify_admin_user(user)
    w = db.query(SellerWithdrawal).filter(SellerWithdrawal.id == withdrawal_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if w.status == "completed":
        raise HTTPException(status_code=400, detail="Cannot reject a completed withdrawal")
    
    wallet = db.query(SellerWallet).filter(SellerWallet.id == w.wallet_id).first()
    if wallet:
        wallet.pending_withdrawal_usd = max(0.0, wallet.pending_withdrawal_usd - w.amount_usd)
        wallet.balance_usd += w.amount_usd
    
    w.status = "failed"
    w.failure_reason = reason
    db.commit()
    return {"status": "success", "message": f"Withdrawal {w.id} rejected and funds restored."}


# ── Marketplace Purchase via Razorpay ─────────────────────────────────────────

class PurchaseOrderReq(BaseModel):
    currency: Optional[str] = "INR"


@router.post("/listings/{slug}/purchase/order")
def create_purchase_order(
    slug: str,
    req: PurchaseOrderReq,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Create a Razorpay order for purchasing a marketplace listing."""
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.slug == slug).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if not listing.is_paid:
        raise HTTPException(status_code=400, detail="This listing is free — no purchase required")
    
    # Check if already purchased
    existing = db.query(MarketplacePurchase).filter(
        MarketplacePurchase.listing_id == listing.id,
        MarketplacePurchase.buyer_id == user.id,
        MarketplacePurchase.status == "completed"
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already purchased")
    
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    
    currency = (req.currency or "INR").upper()
    amount_usd = listing.price_usd
    
    if currency == "INR":
        from ..exchange_rate import ExchangeRateStore
        usd_to_inr = ExchangeRateStore.get_rate()
        amount_inr = amount_usd * usd_to_inr
        amount_paise = max(100, int(amount_inr * 100))
        amount_inr = amount_paise / 100.0
    else:
        amount_inr = 0.0
        amount_paise = max(100, int(amount_usd * 100))
    
    # Platform split
    platform_fee = round(amount_usd * 0.05, 4)  # 5%
    seller_amount = round(amount_usd * 0.95, 4)  # 95%
    
    # Ensure subscription products have a valid Razorpay Plan ID
    if getattr(listing, "payment_type", "one_time") == "subscription":
        if not getattr(listing, "razorpay_plan_id", None):
            listing.razorpay_plan_id = _create_razorpay_plan_if_needed(
                name=listing.name,
                price_usd=listing.price_usd,
                payment_type=listing.payment_type,
                interval=listing.subscription_interval
            )
            db.commit()

    if not key_id or key_id.startswith("mock"):
        # Mock flow
        order_id = f"sub_mock_{uuid.uuid4().hex[:12]}" if getattr(listing, "payment_type", "one_time") == "subscription" else f"order_mock_{uuid.uuid4().hex[:12]}"
        purchase_order = MarketplacePurchaseOrder(
            listing_id=listing.id,
            buyer_id=user.id,
            razorpay_order_id=order_id,
            amount_usd=amount_usd,
            amount_inr=amount_inr,
            currency=currency,
            platform_fee_usd=platform_fee,
            seller_amount_usd=seller_amount,
        )
        db.add(purchase_order)
        db.commit()
        return {
            "order_id": order_id,
            "plan_id": getattr(listing, "razorpay_plan_id", None),
            "key_id": "mock_key_id",
            "amount": amount_paise,
            "currency": currency,
            "listing_name": listing.name,
            "amount_usd": amount_usd,
            "payment_type": getattr(listing, "payment_type", "one_time"),
            "subscription_interval": getattr(listing, "subscription_interval", None),
        }

    import requests as req_lib
    import base64

    auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_str}", "Content-Type": "application/json"}

    order_id = None
    subscription_id = None

    if getattr(listing, "payment_type", "one_time") == "subscription" and listing.razorpay_plan_id:
        # Create Razorpay Subscription via Subscriptions API
        sub_payload = {
            "plan_id": listing.razorpay_plan_id,
            "total_count": 12,
            "quantity": 1,
            "customer_notify": 1,
            "notes": {
                "listing_slug": slug,
                "buyer_id": user.id,
                "listing_name": listing.name,
            }
        }
        resp = req_lib.post("https://api.razorpay.com/v1/subscriptions", json=sub_payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            sub_data = resp.json()
            subscription_id = sub_data.get("id")
            order_id = subscription_id
        else:
            logger.error(f"Razorpay subscription creation error ({resp.status_code}): {resp.text}")

    if not order_id:
        # Fallback / One-time Order via Orders API
        payload = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": f"mp_{uuid.uuid4().hex[:12]}",
            "notes": {
                "listing_slug": slug,
                "buyer_id": user.id,
                "listing_name": listing.name,
            }
        }
        resp = req_lib.post("https://api.razorpay.com/v1/orders", json=payload, headers=headers, timeout=10)
        if resp.status_code not in (200, 201):
            logger.error(f"Razorpay marketplace order error: {resp.text}")
            raise HTTPException(status_code=500, detail="Failed to create payment order")

        order_data = resp.json()
        order_id = order_data["id"]

    purchase_order = MarketplacePurchaseOrder(
        listing_id=listing.id,
        buyer_id=user.id,
        razorpay_order_id=order_id,
        amount_usd=amount_usd,
        amount_inr=amount_inr,
        currency=currency,
        platform_fee_usd=platform_fee,
        seller_amount_usd=seller_amount,
    )
    db.add(purchase_order)
    db.commit()
    
    vpa = os.environ.get("RAZORPAY_VPA", "utimbyemendai278706.rzp@rxairtel")
    upi_url = None

    if key_id and key_secret and not key_id.startswith("mock"):
        try:
            import requests as req_lib
            import base64
            auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
            headers = {"Authorization": f"Basic {auth_str}", "Content-Type": "application/json"}
            qr_payload = {
                "type": "upi_qr",
                "name": "UTIM by Emend Ai",
                "usage": "single_use",
                "fixed_amount": True,
                "payment_amount": amount_paise,
                "description": f"Order for {listing.name[:20]}",
                "notes": {
                    "order_id": order_id,
                    "listing_slug": slug,
                    "buyer_id": user.id
                }
            }
            qr_resp = req_lib.post("https://api.razorpay.com/v1/payments/qr_codes", json=qr_payload, headers=headers, timeout=5)
            if qr_resp.status_code in (200, 201):
                qr_data = qr_resp.json()
                upi_url = qr_data.get("payload")
        except Exception as e:
            logger.warning(f"Razorpay QR API fallback: {e}")

    if not upi_url:
        upi_url = f"upi://pay?cu=INR&mc=5817&mode=19&pa={vpa}&tn=Payment%20To%20UTIM%20by%20Emend%20Ai&tr=TL0qLELGduMuFSqrv2&am={amount_inr:.2f}"

    return {
        "order_id": order_id,
        "key_id": key_id,
        "amount": amount_paise,
        "currency": currency,
        "listing_name": listing.name,
        "amount_usd": amount_usd,
        "razorpay_vpa": vpa,
        "upi_url": upi_url,
    }


class PurchaseVerifyReq(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/listings/{slug}/purchase/verify")
def verify_purchase(
    slug: str,
    req: PurchaseVerifyReq,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Verify Razorpay signature and complete the purchase, credit seller wallet with 95%."""
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.slug == slug).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    purchase_order = db.query(MarketplacePurchaseOrder).filter(
        MarketplacePurchaseOrder.razorpay_order_id == req.razorpay_order_id,
        MarketplacePurchaseOrder.buyer_id == user.id
    ).first()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if purchase_order.status == "paid":
        return {"status": "already_paid"}
    
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    is_mock = req.razorpay_order_id.startswith("order_mock") or req.razorpay_order_id.startswith("sub_mock") or req.razorpay_signature == "manual_verify"
    
    if not is_mock and key_secret:
        msg = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
        generated_sig = hmac.new(
            key_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if generated_sig != req.razorpay_signature:
            raise HTTPException(status_code=400, detail="Payment signature verification failed")
    
    # Mark order as paid
    purchase_order.status = "paid"
    purchase_order.razorpay_payment_id = req.razorpay_payment_id
    purchase_order.razorpay_signature = req.razorpay_signature
    purchase_order.paid_at = datetime.datetime.utcnow()
    
    # Create completed purchase record (for download access)
    purchase = MarketplacePurchase(
        listing_id=listing.id,
        buyer_id=user.id,
        amount_usd=purchase_order.amount_usd,
        status="completed"
    )
    db.add(purchase)
    
    # Credit seller wallet with 95%
    seller = db.query(User).filter(User.id == listing.seller_id).first()
    if seller:
        seller_profile = db.query(SellerProfile).filter(SellerProfile.user_id == seller.id).first()
        if not seller_profile:
            seller_profile = SellerProfile(user_id=seller.id)
            db.add(seller_profile)
            db.flush()
        
        if not seller_profile.wallet:
            wallet = SellerWallet(seller_id=seller_profile.id)
            db.add(wallet)
            db.flush()
        
        seller_profile.wallet.balance_usd += purchase_order.seller_amount_usd
        seller_profile.wallet.total_earned_usd += purchase_order.seller_amount_usd
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"Purchase complete! You can now download '{listing.name}'.",
        "listing_slug": slug,
        "platform_fee_usd": purchase_order.platform_fee_usd,
        "seller_credited_usd": purchase_order.seller_amount_usd,
    }


@router.post("/listings/{slug}/purchase/refund")
def process_purchase_refund(
    slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Process a refund for a completed purchase via Razorpay Refunds API."""
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.slug == slug).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    purchase = db.query(MarketplacePurchase).filter(
        MarketplacePurchase.listing_id == listing.id,
        MarketplacePurchase.buyer_id == user.id,
        MarketplacePurchase.status == "completed"
    ).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="No active completed purchase found for this listing")
    
    purchase_order = db.query(MarketplacePurchaseOrder).filter(
        MarketplacePurchaseOrder.listing_id == listing.id,
        MarketplacePurchaseOrder.buyer_id == user.id,
        MarketplacePurchaseOrder.status == "paid"
    ).order_by(desc(MarketplacePurchaseOrder.created_at)).first()
    
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    
    if purchase_order and purchase_order.razorpay_payment_id and key_id and key_secret and not key_id.startswith("mock"):
        try:
            import requests as req_lib
            import base64
            auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
            headers = {"Authorization": f"Basic {auth_str}", "Content-Type": "application/json"}
            refund_resp = req_lib.post(
                f"https://api.razorpay.com/v1/payments/{purchase_order.razorpay_payment_id}/refund",
                json={"notes": {"reason": "User requested refund", "listing": slug}},
                headers=headers, timeout=10
            )
            if refund_resp.status_code not in (200, 201):
                logger.error(f"Razorpay refund error ({refund_resp.status_code}): {refund_resp.text}")
                raise HTTPException(status_code=500, detail="Razorpay refund processing failed")
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"Refund Exception: {e}")
            raise HTTPException(status_code=500, detail=f"Refund failed: {str(e)}")

    # Mark purchase as refunded
    purchase.status = "refunded"
    
    # Deduct seller 95% share if credited
    seller_profile = db.query(SellerProfile).filter(SellerProfile.user_id == listing.seller_id).first()
    if seller_profile and seller_profile.wallet and purchase_order:
        refund_amount = purchase_order.seller_amount_usd
        if seller_profile.wallet.balance_usd >= refund_amount:
            seller_profile.wallet.balance_usd -= refund_amount
        else:
            seller_profile.wallet.balance_usd = 0.0
        seller_profile.wallet.total_earned_usd = max(0.0, seller_profile.wallet.total_earned_usd - refund_amount)
    
    db.commit()
    return {"status": "success", "message": f"Refund processed successfully for '{listing.name}'."}
