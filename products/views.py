from django.shortcuts import render
from .models import Product, Category, Order, OrderItem
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from .cart import Cart
from django.views.decorators.http import require_POST
from django.conf import settings
from django.urls import reverse
from .paystack import initiate_paystack_payment
from .delivery_fees import DELIVERY_FEES
import uuid
import requests

def home(request):
    recent_products = Product.objects.filter(in_stock=True).order_by('-created_at')[:6]
    categories = Category.objects.all()
    category_products = {}

    for category in categories:
        products = Product.objects.filter(category=category, in_stock=True).order_by('-created_at')[:6]
        category_products[category.slug] = {
            'name': category.name,
            'products': products
        }

    return render(request, 'products/home.html', {
        'recent_products' : recent_products,
        'category_products': category_products,
    })

def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category, in_stock=True).order_by('-created_at')
    return render(request, 'products/category_products.html', {
        'category': category,
        'products': products
    })

def add_to_cart(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))

        product = get_object_or_404(Product, id=product_id)
        cart = Cart(request)
        cart.add(product=product, quantity=quantity)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'cartCount': len(cart)})
        return redirect('cart_view')  # fallback
    return JsonResponse({'status': 'fail'}, status=400)


def cart_view(request):
    cart = Cart(request)
    return render(request, 'products/cart.html', {'cart': cart,'delivery_fees': DELIVERY_FEES})


@require_POST
def update_cart(request):
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))  # convert quantity to int
    product = get_object_or_404(Product, id=product_id)

    cart = Cart(request)
    cart.update(product, quantity)  # Pass product object and quantity
    return redirect('cart_view')


@require_POST
def remove_from_cart(request):
    product_id = request.POST.get('product_id')
    product = get_object_or_404(Product, id=product_id)

    cart = Cart(request)
    cart.remove(product_id)  # Pass product object
    return redirect('cart_view')


@require_POST
def clear_cart(request):
    cart = Cart(request)
    cart.clear()
    return redirect('cart_view')


def process_order(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        payment_method = request.POST.get('payment_method')

        cart_data = request.session.get('cart', {})

        if not cart_data:
            return redirect('cart_view')

        total_amount = 0
        for item in cart_data.values():
            total_amount += float(item['price']) * int(item['quantity'])

        location = request.POST.get('location')
        delivery_fee = DELIVERY_FEES.get(location, 0)

        order = Order.objects.create(
            name=name,
            email=email,
            phone=phone,
            address=address,
            delivery_location=location,
            delivery_fee=delivery_fee,
            total_amount=total_amount + delivery_fee,
            paid=False
        )
        
        for product_id, item in cart_data.items():
            product = get_object_or_404(Product, id=product_id)
            quantity = int(item['quantity'])
            price = float(item['price'])

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=price
            )

        # Save order id in session for payment later
        request.session['order_id'] = order.id

        # Redirect based on payment method
        if payment_method == 'paystack':
            return redirect('initiate_payment')

    return redirect('cart_view')


def initiate_payment(request):
    order_id = request.session.get('order_id')
    if not order_id:
        return redirect('cart_view')

    from .models import Order
    order = Order.objects.get(id=order_id)

    # Generate a unique reference
    reference = str(uuid.uuid4())

    # Save the reference (optional)
    request.session['payment_reference'] = reference

    # Build full callback URL
    callback_url = request.build_absolute_uri(reverse('verify_payment') + f"?order_id={order.id}&reference={reference}")

    # Initiate payment
    payment_url = initiate_paystack_payment(
        email=order.email,
        amount=order.total_amount,
        reference=reference,
        callback_url=callback_url
    )

    if payment_url:
        return redirect(payment_url)
    else:
        return redirect('cart_view')

def verify_payment(request):
    reference = request.GET.get('reference')
    order_id = request.GET.get('order_id')

    if not reference or not order_id:
        return redirect('cart_view')

    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()

        order = get_object_or_404(Order, id=order_id)

        if response_data['status'] and response_data['data']['status'] == 'success':
            order.paid = True
            order.save()

            # Clear cart
            request.session['cart'] = {}

            return render(request, 'products/payment_success.html', {
                'order': order,
                'message': "Your payment was successful! You'll be contacted shortly."
            })
        else:
            return render(request, 'products/payment_failed.html', {
                'order': order,
                'message': "Sorry, your payment was unsuccessful. Please try again."
            })

    except Exception as e:
        return redirect('cart_view')